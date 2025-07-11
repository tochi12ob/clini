import os
import httpx
from dotenv import load_dotenv
from datetime import datetime, timedelta
import base64
import json
from urllib.parse import urlencode, parse_qs, urlparse

load_dotenv()

# Load Epic FHIR credentials from environment variables
EPIC_CLIENT_ID = os.getenv("EPIC_CLIENT_ID")
EPIC_CLIENT_SECRET = os.getenv("EPIC_CLIENT_SECRET")
EPIC_FHIR_BASE_URL = os.getenv("EPIC_FHIR_BASE_URL")  # e.g., https://fhir.epic.com/interconnect-fhir-oauth
EPIC_REDIRECT_URI = os.getenv("EPIC_REDIRECT_URI", "http://localhost:8000/callback")

# In-memory cache for the access token
_access_token = None
_token_expires_at = None

# Token persistence file
TOKEN_FILE = ".epic_token.json"

FHIR_RESOURCE_BASE = f"{EPIC_FHIR_BASE_URL}/api/FHIR/R4"  # <- new constant

def save_token_to_file(token_data: dict):
    """Save token data to file for persistence"""
    try:
        with open(TOKEN_FILE, 'w') as f:
            json.dump(token_data, f)
    except Exception as e:
        print(f"Warning: Could not save token to file: {e}")

def load_token_from_file():
    """Load token data from file"""
    global _access_token, _token_expires_at
    
    try:
        if os.path.exists(TOKEN_FILE):
            with open(TOKEN_FILE, 'r') as f:
                token_data = json.load(f)
            
            _access_token = token_data.get('access_token')
            expires_at_str = token_data.get('expires_at')
            
            if expires_at_str:
                _token_expires_at = datetime.fromisoformat(expires_at_str)
            
            # Check if token is still valid
            if _token_expires_at and datetime.now() >= _token_expires_at:
                print("Stored token has expired")
                _access_token = None
                _token_expires_at = None
                return False
            
            if _access_token:
                print("Loaded valid token from file")
                return True
                
    except Exception as e:
        print(f"Warning: Could not load token from file: {e}")
    
    return False

# Try to load token on import
load_token_from_file()

def get_epic_auth_url(state: str | None = None) -> str:
    """
    Build the SMART-on-FHIR v2 authorization URL for Epic.
    """
    auth_params = {
        "response_type": "code",
        "client_id": EPIC_CLIENT_ID,
        "redirect_uri": EPIC_REDIRECT_URI,
        # user-level scopes + identity + offline
        "scope": (
            "user/Appointment.read "
            "user/DocumentReference.read "
            "openid fhirUser offline_access"
        ),
        "aud": FHIR_RESOURCE_BASE,  # MUST be the data endpoint
    }
    if state:
        auth_params["state"] = state
    return f"{EPIC_FHIR_BASE_URL}/oauth2/authorize?" + urlencode(auth_params)

def exchange_code_for_token(authorization_code: str):
    """
    Exchanges authorization code for access token using Epic's OAuth2 flow.
    
    Args:
        authorization_code (str): Authorization code from Epic OAuth2 callback
        
    Returns:
        dict: Token response or error information
    """
    global _access_token, _token_expires_at
    
    if not EPIC_CLIENT_ID or not EPIC_CLIENT_SECRET or not EPIC_FHIR_BASE_URL:
        raise ValueError("Epic FHIR credentials are not configured in .env file.")
    
    token_url = f"{EPIC_FHIR_BASE_URL}/oauth2/token"
    
    # Create Basic auth header
    credentials = f"{EPIC_CLIENT_ID}:{EPIC_CLIENT_SECRET}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()
    
    headers = {
        "Authorization": f"Basic {encoded_credentials}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    data = {
        "grant_type": "authorization_code",
        "code": authorization_code,
        "redirect_uri": EPIC_REDIRECT_URI
    }
    
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(token_url, headers=headers, data=data)
            response.raise_for_status()
            
            token_data = response.json()
            _access_token = token_data.get("access_token")
            expires_in = token_data.get("expires_in", 3600)
            _token_expires_at = datetime.now() + timedelta(seconds=expires_in)
            
            # Save token to file for persistence
            token_file_data = {
                "access_token": _access_token,
                "expires_at": _token_expires_at.isoformat(),
                "token_type": token_data.get("token_type", "Bearer"),
                "scope": token_data.get("scope"),
                "patient": token_data.get("patient")
            }
            save_token_to_file(token_file_data)
            
            return {
                "success": True,
                "access_token": _access_token,
                "token_type": token_data.get("token_type", "Bearer"),
                "expires_in": expires_in,
                "scope": token_data.get("scope"),
                "patient": token_data.get("patient")
            }
            
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 400:
            raise ValueError(f"Invalid authorization code or client credentials: {e.response.text}")
        elif e.response.status_code == 401:
            raise ValueError("Invalid client credentials")
        raise Exception(f"Token exchange failed: HTTP {e.response.status_code} - {e.response.text}")
    except Exception as e:
        raise Exception(f"Unexpected error during token exchange: {e}")

def get_access_token():
    """
    Returns the current access token, checking if it's still valid.
    
    Returns:
        str: Valid access token
        
    Raises:
        ValueError: If no valid token is available
    """
    global _access_token, _token_expires_at
    
    if not _access_token:
        raise ValueError("No access token available. Please complete OAuth2 flow first.")
    
    if _token_expires_at and datetime.now() >= _token_expires_at:
        raise ValueError("Access token has expired. Please re-authenticate.")
    
    return _access_token

def make_fhir_request(endpoint: str, params: dict = None):
    """
    Makes a FHIR API request to Epic.
    
    Args:
        endpoint (str): FHIR endpoint (e.g., "Appointment", "Patient/123")
        params (dict, optional): Query parameters
        
    Returns:
        dict: FHIR response or error information
    """
    try:
        token = get_access_token()
        api_url = f"{FHIR_RESOURCE_BASE}/{endpoint}"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/fhir+json",
            "Content-Type": "application/fhir+json"
        }
        
        with httpx.Client(timeout=30.0) as client:
            response = client.get(api_url, headers=headers, params=params or {})
            
            if response.status_code == 200:
                return {
                    "success": True,
                    "data": response.json(),
                    "endpoint": endpoint
                }
            elif response.status_code == 401:
                global _access_token, _token_expires_at
                _access_token = None
                _token_expires_at = None
                raise ValueError("Authentication failed - token may be expired")
            elif response.status_code == 403:
                raise PermissionError("Insufficient permissions for this FHIR resource")
            elif response.status_code == 404:
                raise ValueError(f"FHIR resource not found: {endpoint}")
            else:
                raise Exception(f"FHIR API Error: HTTP {response.status_code} - {response.text}")
                
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "endpoint": endpoint
        }

def get_patient_appointments(patient_id: str, start_date: str = None, end_date: str = None):
    """
    Retrieves appointments for a specific patient using FHIR R4.
    
    Args:
        patient_id (str): The patient ID (FHIR Patient resource ID)
        start_date (str, optional): Start date in YYYY-MM-DD format
        end_date (str, optional): End date in YYYY-MM-DD format
        
    Returns:
        dict: Patient appointments or error information
    """
    try:
        params = {
            "patient": patient_id,
            "_sort": "date"
        }
        
        if start_date and end_date:
            params["date"] = f"ge{start_date}&date=le{end_date}"
        elif start_date:
            params["date"] = f"ge{start_date}"
        elif end_date:
            params["date"] = f"le{end_date}"
        
        result = make_fhir_request("Appointment", params)
        
        if result.get("success"):
            fhir_bundle = result.get("data", {})
            appointments = fhir_bundle.get("entry", [])
            
            # Process appointments to extract useful information
            processed_appointments = []
            for entry in appointments:
                appointment = entry.get("resource", {})
                processed_appointments.append({
                    "id": appointment.get("id"),
                    "status": appointment.get("status"),
                    "start": appointment.get("start"),
                    "end": appointment.get("end"),
                    "description": appointment.get("description"),
                    "participant": appointment.get("participant", []),
                    "serviceType": appointment.get("serviceType", []),
                    "appointmentType": appointment.get("appointmentType"),
                    "reasonCode": appointment.get("reasonCode", []),
                    "comment": appointment.get("comment")
                })
            
            return {
                "success": True,
                "patient_id": patient_id,
                "appointments": processed_appointments,
                "count": len(processed_appointments),
                "total": fhir_bundle.get("total", len(processed_appointments))
            }
        else:
            return result
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "patient_id": patient_id
        }

def search_appointments(date_range: str = None, status: str = None, 
                       service_type: str = None, practitioner: str = None):
    """
    Searches for appointments using various FHIR search parameters.
    
    Args:
        date_range (str, optional): Date range in format "YYYY-MM-DD" or "geYYYY-MM-DD"
        status (str, optional): Appointment status (booked, arrived, fulfilled, cancelled, etc.)
        service_type (str, optional): Service type code
        practitioner (str, optional): Practitioner ID
        
    Returns:
        dict: Search results or error information
    """
    try:
        params = {
            "_sort": "date",
            "_count": "50"  # Limit results
        }
        
        if date_range:
            params["date"] = date_range
        if status:
            params["status"] = status
        if service_type:
            params["service-type"] = service_type
        if practitioner:
            params["practitioner"] = practitioner
        
        result = make_fhir_request("Appointment", params)
        
        if result.get("success"):
            fhir_bundle = result.get("data", {})
            appointments = fhir_bundle.get("entry", [])
            
            processed_appointments = []
            for entry in appointments:
                appointment = entry.get("resource", {})
                processed_appointments.append({
                    "id": appointment.get("id"),
                    "status": appointment.get("status"),
                    "start": appointment.get("start"),
                    "end": appointment.get("end"),
                    "description": appointment.get("description"),
                    "participant": appointment.get("participant", []),
                    "serviceType": appointment.get("serviceType", []),
                    "appointmentType": appointment.get("appointmentType"),
                    "reasonCode": appointment.get("reasonCode", [])
                })
            
            return {
                "success": True,
                "appointments": processed_appointments,
                "count": len(processed_appointments),
                "search_params": params,
                "total": fhir_bundle.get("total", len(processed_appointments))
            }
        else:
            return result
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "search_params": params if 'params' in locals() else None
        }

def get_appointment_details(appointment_id: str):
    """
    Retrieves detailed information about a specific appointment.
    
    Args:
        appointment_id (str): The appointment ID (FHIR Appointment resource ID)
        
    Returns:
        dict: Appointment details or error information
    """
    try:
        result = make_fhir_request(f"Appointment/{appointment_id}")
        
        if result.get("success"):
            appointment = result.get("data", {})
            
            return {
                "success": True,
                "appointment": {
                    "id": appointment.get("id"),
                    "status": appointment.get("status"),
                    "start": appointment.get("start"),
                    "end": appointment.get("end"),
                    "description": appointment.get("description"),
                    "participant": appointment.get("participant", []),
                    "serviceType": appointment.get("serviceType", []),
                    "appointmentType": appointment.get("appointmentType"),
                    "reasonCode": appointment.get("reasonCode", []),
                    "comment": appointment.get("comment"),
                    "created": appointment.get("created"),
                    "location": appointment.get("location", []),
                    "priority": appointment.get("priority")
                },
                "appointment_id": appointment_id
            }
        else:
            return result
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "appointment_id": appointment_id
        }

def get_patient_documents(patient_id: str, category: str = None, 
                         date_range: str = None, doc_type: str = None):
    """
    Retrieves clinical documents for a patient using DocumentReference.
    
    Args:
        patient_id (str): The patient ID (FHIR Patient resource ID)
        category (str, optional): Document category code
        date_range (str, optional): Date range in format "YYYY-MM-DD"
        doc_type (str, optional): Document type code
        
    Returns:
        dict: Patient documents or error information
    """
    try:
        params = {
            "patient": patient_id,
            "_sort": "-date",
            "_count": "50"
        }
        
        if category:
            params["category"] = category
        if date_range:
            params["date"] = date_range
        if doc_type:
            params["type"] = doc_type
        
        result = make_fhir_request("DocumentReference", params)
        
        if result.get("success"):
            fhir_bundle = result.get("data", {})
            documents = fhir_bundle.get("entry", [])
            
            processed_documents = []
            for entry in documents:
                doc = entry.get("resource", {})
                processed_documents.append({
                    "id": doc.get("id"),
                    "status": doc.get("status"),
                    "type": doc.get("type", {}),
                    "category": doc.get("category", []),
                    "subject": doc.get("subject", {}),
                    "date": doc.get("date"),
                    "author": doc.get("author", []),
                    "description": doc.get("description"),
                    "content": doc.get("content", []),
                    "context": doc.get("context", {}),
                    "created": doc.get("created")
                })
            
            return {
                "success": True,
                "patient_id": patient_id,
                "documents": processed_documents,
                "count": len(processed_documents),
                "total": fhir_bundle.get("total", len(processed_documents))
            }
        else:
            return result
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "patient_id": patient_id
        }

def get_document_content(document_id: str):
    """
    Retrieves the content of a specific clinical document.
    
    Args:
        document_id (str): The document ID (FHIR DocumentReference resource ID)
        
    Returns:
        dict: Document content or error information
    """
    try:
        result = make_fhir_request(f"DocumentReference/{document_id}")
        
        if result.get("success"):
            document = result.get("data", {})
            
            return {
                "success": True,
                "document": {
                    "id": document.get("id"),
                    "status": document.get("status"),
                    "type": document.get("type", {}),
                    "category": document.get("category", []),
                    "subject": document.get("subject", {}),
                    "date": document.get("date"),
                    "author": document.get("author", []),
                    "description": document.get("description"),
                    "content": document.get("content", []),
                    "context": document.get("context", {}),
                    "securityLabel": document.get("securityLabel", [])
                },
                "document_id": document_id
            }
        else:
            return result
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "document_id": document_id
        }

def search_patients_by_identifier(identifier: str, identifier_system: str = None):
    """
    Searches for patients by identifier (MRN, SSN, etc.).
    
    Args:
        identifier (str): Patient identifier value
        identifier_system (str, optional): Identifier system/namespace
        
    Returns:
        dict: Patient search results or error information
    """
    try:
        params = {}
        if identifier_system:
            params["identifier"] = f"{identifier_system}|{identifier}"
        else:
            params["identifier"] = identifier
        
        result = make_fhir_request("Patient", params)
        
        if result.get("success"):
            fhir_bundle = result.get("data", {})
            patients = fhir_bundle.get("entry", [])
            
            processed_patients = []
            for entry in patients:
                patient = entry.get("resource", {})
                processed_patients.append({
                    "id": patient.get("id"),
                    "active": patient.get("active"),
                    "name": patient.get("name", []),
                    "identifier": patient.get("identifier", []),
                    "telecom": patient.get("telecom", []),
                    "gender": patient.get("gender"),
                    "birthDate": patient.get("birthDate"),
                    "address": patient.get("address", [])
                })
            
            return {
                "success": True,
                "patients": processed_patients,
                "count": len(processed_patients),
                "search_identifier": identifier,
                "total": fhir_bundle.get("total", len(processed_patients))
            }
        else:
            return result
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "identifier": identifier
        }

def test_fhir_connection():
    """
    Tests the FHIR connection by making a simple metadata request.
    
    Returns:
        dict: Connection test result
    """
    try:
        if not _access_token:
            return {
                "success": False,
                "error": "No access token available. Please complete OAuth2 flow first.",
                "auth_url": get_epic_auth_url("test_state") if EPIC_CLIENT_ID and EPIC_FHIR_BASE_URL else None
            }
        
        # Test with a metadata request (doesn't require specific permissions)
        result = make_fhir_request("metadata")
        
        if result.get("success"):
            metadata = result.get("data", {})
            return {
                "success": True,
                "message": "Successfully connected to Epic FHIR API",
                "fhir_version": metadata.get("fhirVersion"),
                "software": metadata.get("software", {}),
                "implementation": metadata.get("implementation", {})
            }
        else:
            return result
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

# === EPIC APPOINTMENT BOOKING FUNCTIONS ===

def find_available_slots(practitioner_id: str = None, start_date: str = None, 
                        end_date: str = None, service_type: str = None, 
                        location_id: str = None, duration: int = None):
    """
    Finds available appointment slots using Epic's Appointment.$find operation.
    
    Args:
        practitioner_id (str, optional): Practitioner ID to search for
        start_date (str, optional): Start date in YYYY-MM-DD format
        end_date (str, optional): End date in YYYY-MM-DD format
        service_type (str, optional): Service type code
        location_id (str, optional): Location ID
        duration (int, optional): Appointment duration in minutes
        
    Returns:
        dict: Available slots or error information
    """
    try:
        params = {
            "_count": "50"
        }
        
        if practitioner_id:
            params["practitioner"] = practitioner_id
        if start_date:
            params["start"] = f"ge{start_date}"
        if end_date:
            params["start"] = f"le{end_date}"
        if service_type:
            params["service-type"] = service_type
        if location_id:
            params["location"] = location_id
        if duration:
            params["duration"] = duration
            
        # Use Epic's $find operation for appointment slots
        result = make_fhir_request("Appointment/$find", params)
        
        if result.get("success"):
            fhir_bundle = result.get("data", {})
            slots = fhir_bundle.get("entry", [])
            
            processed_slots = []
            for entry in slots:
                slot = entry.get("resource", {})
                processed_slots.append({
                    "id": slot.get("id"),
                    "start": slot.get("start"),
                    "end": slot.get("end"),
                    "status": slot.get("status"),
                    "serviceType": slot.get("serviceType", []),
                    "practitioner": slot.get("participant", []),
                    "location": slot.get("location"),
                    "duration": slot.get("minutesDuration")
                })
            
            return {
                "success": True,
                "available_slots": processed_slots,
                "count": len(processed_slots),
                "search_params": params
            }
        else:
            return result
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def book_fhir_appointment(slot_id: str, patient_id: str, practitioner_id: str = None,
                         start_time: str = None, end_time: str = None,
                         reason: str = None, comment: str = None):
    """
    Books an appointment using Epic's Appointment.$book operation.
    
    Args:
        slot_id (str): The slot ID to book
        patient_id (str): Patient ID (FHIR Patient resource ID)
        practitioner_id (str, optional): Practitioner ID
        start_time (str, optional): Start time in ISO format
        end_time (str, optional): End time in ISO format
        reason (str, optional): Reason for appointment
        comment (str, optional): Additional comments
        
    Returns:
        dict: Booking result or error information
    """
    try:
        # Prepare appointment resource for booking
        appointment_data = {
            "resourceType": "Appointment",
            "status": "booked",
            "participant": [
                {
                    "actor": {
                        "reference": f"Patient/{patient_id}"
                    },
                    "status": "accepted"
                }
            ]
        }
        
        if slot_id:
            appointment_data["slot"] = [{"reference": f"Slot/{slot_id}"}]
        
        if practitioner_id:
            appointment_data["participant"].append({
                "actor": {
                    "reference": f"Practitioner/{practitioner_id}"
                },
                "status": "accepted"
            })
            
        if start_time:
            appointment_data["start"] = start_time
        if end_time:
            appointment_data["end"] = end_time
        if reason:
            appointment_data["reasonCode"] = [{"text": reason}]
        if comment:
            appointment_data["comment"] = comment
        
        # Use Epic's $book operation
        token = get_access_token()
        api_url = f"{FHIR_RESOURCE_BASE}/Appointment/$book"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/fhir+json",
            "Content-Type": "application/fhir+json"
        }
        
        with httpx.Client(timeout=30.0) as client:
            response = client.post(api_url, headers=headers, json=appointment_data)
            
            if response.status_code in [200, 201]:
                appointment = response.json()
                return {
                    "success": True,
                    "appointment": appointment,
                    "appointment_id": appointment.get("id"),
                    "patient_id": patient_id,
                    "slot_id": slot_id
                }
            else:
                raise Exception(f"Booking failed: HTTP {response.status_code} - {response.text}")
                
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "patient_id": patient_id,
            "slot_id": slot_id
        }

# === PATIENT MANAGEMENT FUNCTIONS ===

def search_patients(first_name: str = None, last_name: str = None,
                   date_of_birth: str = None, phone: str = None,
                   identifier: str = None, limit: int = 10):
    """
    Search for patients using FHIR Patient.Search.
    
    Args:
        first_name (str, optional): Patient's first name
        last_name (str, optional): Patient's last name
        date_of_birth (str, optional): DOB in YYYY-MM-DD format
        phone (str, optional): Phone number
        identifier (str, optional): Patient identifier (MRN, etc.)
        limit (int): Maximum number of results
        
    Returns:
        dict: Patient search results or error information
    """
    try:
        params = {"_count": str(limit)}
        
        if first_name:
            params["given"] = first_name
        if last_name:
            params["family"] = last_name
        if date_of_birth:
            params["birthdate"] = date_of_birth
        if phone:
            params["telecom"] = phone
        if identifier:
            params["identifier"] = identifier
            
        result = make_fhir_request("Patient", params)
        
        if result.get("success"):
            fhir_bundle = result.get("data", {})
            patients = fhir_bundle.get("entry", [])
            
            processed_patients = []
            for entry in patients:
                patient = entry.get("resource", {})
                processed_patients.append({
                    "id": patient.get("id"),
                    "active": patient.get("active"),
                    "name": patient.get("name", []),
                    "identifier": patient.get("identifier", []),
                    "telecom": patient.get("telecom", []),
                    "gender": patient.get("gender"),
                    "birthDate": patient.get("birthDate"),
                    "address": patient.get("address", [])
                })
            
            return {
                "success": True,
                "patients": processed_patients,
                "count": len(processed_patients),
                "search_params": params
            }
        else:
            return result
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def get_patient_details(patient_id: str):
    """
    Retrieves detailed information about a specific patient.
    
    Args:
        patient_id (str): The patient ID (FHIR Patient resource ID)
        
    Returns:
        dict: Patient details or error information
    """
    try:
        result = make_fhir_request(f"Patient/{patient_id}")
        
        if result.get("success"):
            patient = result.get("data", {})
            
            return {
                "success": True,
                "patient": {
                    "id": patient.get("id"),
                    "active": patient.get("active"),
                    "name": patient.get("name", []),
                    "identifier": patient.get("identifier", []),
                    "telecom": patient.get("telecom", []),
                    "gender": patient.get("gender"),
                    "birthDate": patient.get("birthDate"),
                    "address": patient.get("address", []),
                    "maritalStatus": patient.get("maritalStatus"),
                    "contact": patient.get("contact", []),
                    "communication": patient.get("communication", [])
                },
                "patient_id": patient_id
            }
        else:
            return result
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "patient_id": patient_id
        }

# === PRACTITIONER MANAGEMENT FUNCTIONS ===

def search_practitioners(name: str = None, specialty: str = None,
                        location_id: str = None, limit: int = 20):
    """
    Search for practitioners using FHIR Practitioner.Search.
    
    Args:
        name (str, optional): Practitioner name
        specialty (str, optional): Specialty code
        location_id (str, optional): Location ID
        limit (int): Maximum number of results
        
    Returns:
        dict: Practitioner search results or error information
    """
    try:
        params = {"_count": str(limit)}
        
        if name:
            params["name"] = name
        if specialty:
            params["specialty"] = specialty
        if location_id:
            params["location"] = location_id
            
        result = make_fhir_request("Practitioner", params)
        
        if result.get("success"):
            fhir_bundle = result.get("data", {})
            practitioners = fhir_bundle.get("entry", [])
            
            processed_practitioners = []
            for entry in practitioners:
                practitioner = entry.get("resource", {})
                processed_practitioners.append({
                    "id": practitioner.get("id"),
                    "active": practitioner.get("active"),
                    "name": practitioner.get("name", []),
                    "identifier": practitioner.get("identifier", []),
                    "telecom": practitioner.get("telecom", []),
                    "address": practitioner.get("address", []),
                    "gender": practitioner.get("gender"),
                    "qualification": practitioner.get("qualification", [])
                })
            
            return {
                "success": True,
                "practitioners": processed_practitioners,
                "count": len(processed_practitioners)
            }
        else:
            return result
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def get_practitioner_details(practitioner_id: str):
    """
    Retrieves detailed information about a specific practitioner.
    
    Args:
        practitioner_id (str): The practitioner ID
        
    Returns:
        dict: Practitioner details or error information
    """
    try:
        result = make_fhir_request(f"Practitioner/{practitioner_id}")
        
        if result.get("success"):
            practitioner = result.get("data", {})
            
            return {
                "success": True,
                "practitioner": practitioner,
                "practitioner_id": practitioner_id
            }
        else:
            return result
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "practitioner_id": practitioner_id
        }

# === COVERAGE/INSURANCE FUNCTIONS ===

def get_patient_coverage(patient_id: str):
    """
    Retrieves insurance coverage information for a patient.
    
    Args:
        patient_id (str): The patient ID
        
    Returns:
        dict: Coverage information or error information
    """
    try:
        params = {
            "patient": patient_id,
            "_count": "10"
        }
        
        result = make_fhir_request("Coverage", params)
        
        if result.get("success"):
            fhir_bundle = result.get("data", {})
            coverages = fhir_bundle.get("entry", [])
            
            processed_coverages = []
            for entry in coverages:
                coverage = entry.get("resource", {})
                processed_coverages.append({
                    "id": coverage.get("id"),
                    "status": coverage.get("status"),
                    "type": coverage.get("type"),
                    "policyHolder": coverage.get("policyHolder"),
                    "subscriber": coverage.get("subscriber"),
                    "beneficiary": coverage.get("beneficiary"),
                    "relationship": coverage.get("relationship"),
                    "period": coverage.get("period"),
                    "payor": coverage.get("payor", []),
                    "class": coverage.get("class", [])
                })
            
            return {
                "success": True,
                "patient_id": patient_id,
                "coverages": processed_coverages,
                "count": len(processed_coverages)
            }
        else:
            return result
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "patient_id": patient_id
        }

# === LOCATION & ORGANIZATION FUNCTIONS ===

def get_location_details(location_id: str):
    """
    Retrieves detailed information about a location.
    
    Args:
        location_id (str): The location ID
        
    Returns:
        dict: Location details or error information
    """
    try:
        result = make_fhir_request(f"Location/{location_id}")
        
        if result.get("success"):
            location = result.get("data", {})
            
            return {
                "success": True,
                "location": location,
                "location_id": location_id
            }
        else:
            return result
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "location_id": location_id
        }

def get_organization_details(organization_id: str):
    """
    Retrieves detailed information about an organization.
    
    Args:
        organization_id (str): The organization ID
        
    Returns:
        dict: Organization details or error information
    """
    try:
        result = make_fhir_request(f"Organization/{organization_id}")
        
        if result.get("success"):
            organization = result.get("data", {})
            
            return {
                "success": True,
                "organization": organization,
                "organization_id": organization_id
            }
        else:
            return result
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "organization_id": organization_id
        }

if __name__ == "__main__":
    """
    Simple connection test and setup guide for Epic FHIR client
    """
    print("🏥 Epic FHIR R4 Client - MVP Edition")
    print("=" * 60)
    
    # Check environment configuration
    print("📋 Environment Configuration:")
    print(f"EPIC_CLIENT_ID: {'✓ Set' if EPIC_CLIENT_ID else '❌ Missing'}")
    print(f"EPIC_CLIENT_SECRET: {'✓ Set' if EPIC_CLIENT_SECRET else '❌ Missing'}")
    print(f"EPIC_FHIR_BASE_URL: {EPIC_FHIR_BASE_URL if EPIC_FHIR_BASE_URL else '❌ Missing'}")
    print(f"EPIC_REDIRECT_URI: {EPIC_REDIRECT_URI}")
    
    if not (EPIC_CLIENT_ID and EPIC_CLIENT_SECRET and EPIC_FHIR_BASE_URL):
        print("\n❌ Missing required environment variables!")
        print("Please set: EPIC_CLIENT_ID, EPIC_CLIENT_SECRET, EPIC_FHIR_BASE_URL")
        print("\n📝 Setup Steps:")
        print("1. Complete your Epic App Orchard registration")
        print("2. Get your client credentials from Epic")
        print("3. Set environment variables in .env file")
        print("4. Complete OAuth2 flow to get access token")
        exit(1)
    
    # Test connection (will require OAuth2 flow first)
    print("\n🔗 Testing FHIR connection...")
    result = test_fhir_connection()
    
    if result.get("success"):
        print("✅ Connection successful!")
        print(f"FHIR Version: {result.get('fhir_version', 'N/A')}")
        print("\n🚀 Epic FHIR client is ready for use!")
    else:
        print(f"❌ Connection failed: {result.get('error', 'Unknown error')}")
        if result.get("auth_url"):
            print(f"\n🔐 Complete OAuth2 flow first:")
            print(f"Visit: {result.get('auth_url')}")
        print("\n🔧 Please complete authentication and try again.")
    
    print("\n" + "=" * 60)
    print("🎯 Available MVP FHIR Functions:")
    print("\n📅 Appointment Management:")
    print("- find_available_slots() - Find open appointment slots")
    print("- book_fhir_appointment() - Book appointments")
    print("- get_patient_appointments() - Patient appointment history")
    print("- search_appointments() - Search all appointments")
    print("- get_appointment_details() - Specific appointment info")
    
    print("\n👥 Patient Management:")
    print("- search_patients() - Find patients by demographics")
    print("- get_patient_details() - Complete patient information")
    print("- search_patients_by_identifier() - Find by MRN/ID")
    print("- get_patient_coverage() - Insurance information")
    
    print("\n👨‍⚕️ Provider Management:")
    print("- search_practitioners() - Find providers")
    print("- get_practitioner_details() - Provider information")
    
    print("\n🏢 Organization & Location:")
    print("- get_location_details() - Clinic/office information")
    print("- get_organization_details() - Health system info")
    
    print("\n📄 Clinical Documents:")
    print("- get_patient_documents() - Clinical notes/documents")
    print("- get_document_content() - Document details")
    
    print("\n🔧 System:")
    print("- test_fhir_connection() - Connection testing")
    
    print("\n" + "=" * 60)
    print("✅ Epic APIs Enabled in Console:")
    print("- Appointment.$find, Appointment.$book")
    print("- Patient.Read, Patient.Search, Patient.$match")
    print("- Practitioner.Read, Practitioner.Search")
    print("- PractitionerRole.Read, PractitionerRole.Search") 
    print("- Schedule.Read, Slot.Read")
    print("- Location.Read, Organization.Read")
    print("- Coverage.Read, Coverage.Search")
    print("- DocumentReference.Read")
    print("\nNote: OAuth2 authentication required before using FHIR functions.") 