import os
import httpx
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

# Load credentials from environment variables
CLIENT_ID = os.getenv("ATHENA_CLIENT_ID")
CLIENT_SECRET = os.getenv("ATHENA_CLIENT_SECRET")
BASE_URL = os.getenv("ATHENA_API_BASE_URL")
DEFAULT_PRACTICE_ID = os.getenv("ATHENA_PRACTICE_ID")

# In-memory cache for the access token
_access_token = None

def get_access_token():
    """
    Retrieves an OAuth2 access token from AthenaHealth.
    Caches the token in memory to avoid re-authenticating for every call.
    """
    global _access_token
    if _access_token:
        return _access_token

    if not CLIENT_ID or not CLIENT_SECRET or not BASE_URL:
        raise ValueError("AthenaHealth API credentials are not configured in .env file.")

    auth_url = f"{BASE_URL}/oauth2/v1/token"
    
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope": "athena/service/Athenanet.MDP.*"
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(auth_url, headers=headers, data=data)
            response.raise_for_status()
            
            token_data = response.json()
            _access_token = token_data.get("access_token")
            
            if not _access_token:
                raise ValueError("Failed to retrieve access token from AthenaHealth.")
            
            return _access_token
    except httpx.ConnectError as e:
        raise ConnectionError(f"Cannot connect to AthenaHealth API: {e}")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            raise ValueError("Invalid AthenaHealth credentials")
        elif e.response.status_code == 403:
            raise PermissionError("Insufficient permissions for AthenaHealth API")
        raise
    except Exception as e:
        raise Exception(f"Unexpected error during authentication: {e}")

def check_availability(department_id: str, start_date: str, end_date: str, 
                      practice_id: str = None, reason_id: int = -1, provider_id: str = None, limit: int = 10):
    """
    Checks for open appointment slots in AthenaHealth.
    
    Args:
        department_id (str): The department ID to check availability for
        start_date (str): Start date in MM/DD/YYYY format
        end_date (str): End date in MM/DD/YYYY format  
        practice_id (str): Practice ID (defaults to environment variable)
        reason_id (int): Appointment reason ID (-1 for any reason)
        limit (int): Maximum number of slots to return
        
    Returns:
        dict: Available appointment slots or error information
    """
    if not practice_id:
        practice_id = DEFAULT_PRACTICE_ID
                
    try:
        token = get_access_token()
        api_url = f"{BASE_URL}/v1/{practice_id}/appointments/open"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        params = {
            "departmentid": department_id,
            "startdate": start_date,
            "enddate": end_date,
            "reasonid": reason_id,
            "limit": limit
        }
        
        if provider_id:
            params["providerid"] = provider_id
        
        with httpx.Client(timeout=30.0) as client:
            response = client.get(api_url, headers=headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                appointments = data.get("appointments", [])
                
                return {
                    "success": True,
                    "available_slots": len(appointments),
                    "appointments": appointments,
                    "department_id": department_id,
                    "date_range": f"{start_date} to {end_date}"
                }
                    
            elif response.status_code == 401:
                global _access_token
                _access_token = None
                raise ValueError("Authentication failed - token expired")
                
            elif response.status_code == 404:
                raise ValueError(f"Department {department_id} or practice {practice_id} not found")
                
            else:
                raise Exception(f"API Error: HTTP {response.status_code} - {response.text}")
                
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "department_id": department_id,
            "date_range": f"{start_date} to {end_date}"
        }

def get_patient_details(patient_id: str, practice_id: str = None):
    """
    Retrieves detailed information about a patient.
    
    Args:
        patient_id (str): The patient ID to retrieve details for
        practice_id (str): Practice ID (defaults to environment variable)
        
    Returns:
        dict: Patient details or error information
    """
    if not practice_id:
        practice_id = DEFAULT_PRACTICE_ID
        
    try:
        token = get_access_token()
        api_url = f"{BASE_URL}/v1/{practice_id}/patients/{patient_id}"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        with httpx.Client(timeout=30.0) as client:
            response = client.get(api_url, headers=headers)
            
            if response.status_code == 200:
                patient_data = response.json()
                return {
                    "success": True,
                    "patient": patient_data,
                    "patient_id": patient_id
                }
                
            elif response.status_code == 404:
                raise ValueError(f"Patient {patient_id} not found")
                
            elif response.status_code == 401:
                global _access_token
                _access_token = None
                raise ValueError("Authentication failed")
                
            else:
                raise Exception(f"API Error: HTTP {response.status_code} - {response.text}")
                
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "patient_id": patient_id
        }

def get_patient_insurance(patient_id: str, practice_id: str = None):
    """
    Retrieves insurance information for a patient.
    
    Args:
        patient_id (str): The patient ID to retrieve insurance for
        practice_id (str): Practice ID (defaults to environment variable)
        
    Returns:
        dict: Insurance information or error information
    """
    if not practice_id:
        practice_id = DEFAULT_PRACTICE_ID
        
    try:
        token = get_access_token()
        api_url = f"{BASE_URL}/v1/{practice_id}/patients/{patient_id}/insurances"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        with httpx.Client(timeout=30.0) as client:
            response = client.get(api_url, headers=headers)
            
            if response.status_code == 200:
                insurance_data = response.json()
                insurances = insurance_data.get("insurances", [])
                return {
                    "success": True,
                    "insurances": insurances,
                    "patient_id": patient_id,
                    "count": len(insurances)
                }
                
            elif response.status_code == 404:
                raise ValueError(f"No insurance information found for patient {patient_id}")
                
            elif response.status_code == 401:
                global _access_token
                _access_token = None
                raise ValueError("Authentication failed")
                
            else:
                raise Exception(f"API Error: HTTP {response.status_code} - {response.text}")
                
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "patient_id": patient_id
        }

def get_patient_appointment_reasons(department_id: str = None, provider_id: str = None, 
                                   patient_type: str = None, practice_id: str = None):
    """
    Gets available patient appointment reasons for booking.
    
    Args:
        department_id (str, optional): Filter by department ID
        provider_id (str, optional): Filter by provider ID
        patient_type (str, optional): 'new', 'existing', or None for all
        practice_id (str): Practice ID (defaults to environment variable)
        
    Returns:
        dict: Available appointment reasons or error information
    """
    if not practice_id:
        practice_id = DEFAULT_PRACTICE_ID
        
    try:
        token = get_access_token()
        
        # Choose endpoint based on patient type
        if patient_type == "new":
            api_url = f"{BASE_URL}/v1/{practice_id}/patientappointmentreasons/newpatient"
        elif patient_type == "existing":
            api_url = f"{BASE_URL}/v1/{practice_id}/patientappointmentreasons/existingpatient"
        else:
            api_url = f"{BASE_URL}/v1/{practice_id}/patientappointmentreasons"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        params = {}
        if department_id:
            params["departmentid"] = department_id
        if provider_id:
            params["providerid"] = provider_id
        
        with httpx.Client(timeout=30.0) as client:
            response = client.get(api_url, headers=headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                reasons = data.get("patientappointmentreasons", [])
                return {
                    "success": True,
                    "appointment_reasons": reasons,
                    "count": len(reasons),
                    "department_id": department_id,
                    "patient_type": patient_type
                }
                
            elif response.status_code == 401:
                global _access_token
                _access_token = None
                raise ValueError("Authentication failed")
                
            else:
                raise Exception(f"API Error: HTTP {response.status_code} - {response.text}")
                
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "department_id": department_id,
            "patient_type": patient_type
        }

def get_appointment_types(department_id: str, practice_id: str = None):
    """
    Gets available appointment types for a department.
    
    Args:
        department_id (str): The department ID
        practice_id (str): Practice ID (defaults to environment variable)
        
    Returns:
        dict: Available appointment types or error information
    """
    if not practice_id:
        practice_id = DEFAULT_PRACTICE_ID
        
    try:
        token = get_access_token()
        api_url = f"{BASE_URL}/v1/{practice_id}/appointmenttypes"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        params = {
            "departmentid": department_id
        }
        
        with httpx.Client(timeout=30.0) as client:
            response = client.get(api_url, headers=headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                appointment_types = data.get("appointmenttypes", [])
                return {
                    "success": True,
                    "appointment_types": appointment_types,
                    "department_id": department_id,
                    "count": len(appointment_types)
                }
                
            elif response.status_code == 401:
                global _access_token
                _access_token = None
                raise ValueError("Authentication failed")
                
            else:
                raise Exception(f"API Error: HTTP {response.status_code} - {response.text}")
                
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "department_id": department_id
        }

def book_appointment(appointment_id: str, patient_id: str, practice_id: str = None, 
                    reason: str = None, insurance_id: str = None, appointment_type_id: str = None,
                    reason_id: str = None):
    """
    Books an existing open appointment slot for a patient.
    
    Args:
        appointment_id (str): The appointment ID from available slots
        patient_id (str): The patient ID to book for
        practice_id (str): Practice ID (defaults to environment variable)
        reason (str, optional): Reason for the appointment (legacy)
        insurance_id (str, optional): Insurance ID to use
        appointment_type_id (str, optional): Appointment type ID (legacy)
        reason_id (str, optional): Patient appointment reason ID (preferred)
        
    Returns:
        dict: Booked appointment details or error information
    """
    if not practice_id:
        practice_id = DEFAULT_PRACTICE_ID
        
    try:
        token = get_access_token()
        api_url = f"{BASE_URL}/v1/{practice_id}/appointments/{appointment_id}"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        booking_data = {
            "patientid": patient_id
        }
        
        # Prefer reasonid over appointmenttypeid (AthenaHealth best practice)
        if reason_id:
            booking_data["reasonid"] = reason_id
        elif appointment_type_id:
            booking_data["appointmenttypeid"] = appointment_type_id
        elif reason:
            booking_data["appointmentreason"] = reason
            
        if insurance_id:
            booking_data["insuranceid"] = insurance_id
            
        # Debug: log what we're sending
        print(f"Booking data being sent: {booking_data}")
        
        with httpx.Client(timeout=30.0) as client:
            response = client.put(api_url, headers=headers, data=booking_data)
            
            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "appointment": result,
                    "patient_id": patient_id,
                    "appointment_id": appointment_id
                }
                
            elif response.status_code == 409:
                raise ValueError("Appointment slot is no longer available")
                
            elif response.status_code == 400:
                raise ValueError(f"Invalid booking data: {response.text}")
                
            elif response.status_code == 404:
                raise ValueError(f"Appointment {appointment_id} not found or not available")
                
            elif response.status_code == 401:
                global _access_token
                _access_token = None
                raise ValueError("Authentication failed")
                
            else:
                raise Exception(f"API Error: HTTP {response.status_code} - {response.text}")
                
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "patient_id": patient_id,
            "appointment_id": appointment_id
        }

def create_appointment(patient_id: str, department_id: str, appointment_date: str, 
                      appointment_time: str = None, appointment_type_id: str = None, 
                      provider_id: str = None, practice_id: str = None, 
                      reason: str = None):
    """
    Creates a new appointment for a patient by finding and booking an available slot.
    
    Args:
        patient_id (str): The patient ID
        department_id (str): The department ID
        appointment_date (str): Date in MM/DD/YYYY format
        appointment_time (str, optional): Preferred time in HH:MM format
        appointment_type_id (str, optional): Preferred appointment type ID
        provider_id (str, optional): Preferred provider ID
        practice_id (str): Practice ID (defaults to environment variable)
        reason (str, optional): Reason for the appointment
        
    Returns:
        dict: Created appointment details or error information
    """
    if not practice_id:
        practice_id = DEFAULT_PRACTICE_ID
        
    try:
        # Find available slots
        availability = check_availability(
            department_id=department_id,
            start_date=appointment_date,
            end_date=appointment_date,
            practice_id=practice_id,
            limit=50
        )
        
        if not availability.get("success") or availability.get("available_slots", 0) == 0:
            return {
                "success": False,
                "error": f"No appointment slots available on {appointment_date}"
            }
        
        # Find matching slot
        appointments = availability.get("appointments", [])
        target_slot = None
        
        for slot in appointments:
            # Match criteria
            time_match = not appointment_time or slot.get("starttime") == appointment_time
            type_match = not appointment_type_id or str(slot.get("appointmenttypeid")) == str(appointment_type_id)
            provider_match = not provider_id or str(slot.get("providerid")) == str(provider_id)
            
            if time_match and type_match and provider_match:
                target_slot = slot
                break
        
        if not target_slot:
            # Use first available slot if no exact match
            target_slot = appointments[0]
        
        # Book the slot
        booking_result = book_appointment(
            appointment_id=str(target_slot.get("appointmentid")),
            patient_id=patient_id,
            practice_id=practice_id,
            reason=reason
        )
        
        if booking_result.get("success"):
            return {
                "success": True,
                "appointment": booking_result.get("appointment"),
                "patient_id": patient_id,
                "appointment_date": appointment_date,
                "booked_slot": target_slot
            }
        else:
            return booking_result
                
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "patient_id": patient_id,
            "department_id": department_id,
            "appointment_date": appointment_date
        }

def update_appointment(appointment_id: str, practice_id: str = None, 
                      new_date: str = None, new_time: str = None, 
                      new_provider_id: str = None, new_reason: str = None):
    """
    Updates an existing appointment.
    
    Args:
        appointment_id (str): The appointment ID to update
        practice_id (str): Practice ID (defaults to environment variable)
        new_date (str, optional): New date in MM/DD/YYYY format
        new_time (str, optional): New time in HH:MM format
        new_provider_id (str, optional): New provider ID
        new_reason (str, optional): New reason for appointment
        
    Returns:
        dict: Updated appointment details or error information
    """
    if not practice_id:
        practice_id = DEFAULT_PRACTICE_ID
        
    try:
        token = get_access_token()
        api_url = f"{BASE_URL}/v1/{practice_id}/appointments/{appointment_id}"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        update_data = {}
        if new_date:
            update_data["appointmentdate"] = new_date
        if new_time:
            update_data["appointmenttime"] = new_time
        if new_provider_id:
            update_data["providerid"] = new_provider_id
        if new_reason:
            update_data["reason"] = new_reason
            
        if not update_data:
            raise ValueError("No update parameters provided")
        
        with httpx.Client(timeout=30.0) as client:
            response = client.put(api_url, headers=headers, data=update_data)
            
            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "appointment": result,
                    "appointment_id": appointment_id,
                    "updates": update_data
                }
                
            elif response.status_code == 404:
                raise ValueError(f"Appointment {appointment_id} not found")
                
            elif response.status_code == 400:
                raise ValueError(f"Invalid update data: {response.text}")
                
            elif response.status_code == 409:
                raise ValueError("The requested time slot is not available")
                
            elif response.status_code == 401:
                global _access_token
                _access_token = None
                raise ValueError("Authentication failed")
                
            else:
                raise Exception(f"API Error: HTTP {response.status_code} - {response.text}")
                
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "appointment_id": appointment_id
        }

def search_patients(first_name: str = None, last_name: str = None, 
                   date_of_birth: str = None, phone: str = None,
                   practice_id: str = None, limit: int = 10):
    """
    Search for patients by various criteria.
    
    Args:
        first_name (str, optional): Patient's first name
        last_name (str, optional): Patient's last name
        date_of_birth (str, optional): DOB in MM/DD/YYYY format
        phone (str, optional): Phone number
        practice_id (str): Practice ID (defaults to environment variable)
        limit (int): Maximum number of results (default 10)
        
    Returns:
        dict: Patient search results or error information
    """
    if not practice_id:
        practice_id = DEFAULT_PRACTICE_ID
        
    try:
        token = get_access_token()
        api_url = f"{BASE_URL}/v1/{practice_id}/patients"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        params = {"limit": limit}
        if first_name:
            params["firstname"] = first_name
        if last_name:
            params["lastname"] = last_name
        if date_of_birth:
            params["dob"] = date_of_birth
        if phone:
            params["homephone"] = phone
            
        if len(params) == 1:
            raise ValueError("At least one search parameter is required")
        
        with httpx.Client(timeout=30.0) as client:
            response = client.get(api_url, headers=headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                patients = data.get("patients", [])
                return {
                    "success": True,
                    "patients": patients,
                    "count": len(patients),
                    "search_criteria": params
                }
                
            elif response.status_code == 401:
                global _access_token
                _access_token = None
                raise ValueError("Authentication failed")
                
            else:
                raise Exception(f"API Error: HTTP {response.status_code} - {response.text}")
                
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def update_patient(patient_id: str, first_name: str = None, last_name: str = None,
                  phone: str = None, email: str = None, address: str = None,
                  city: str = None, state: str = None, zip_code: str = None,
                  emergency_contact_name: str = None, emergency_contact_phone: str = None,
                  practice_id: str = None):
    """
    Updates an existing patient's information.
    
    Args:
        patient_id (str): The patient ID to update (required)
        first_name (str, optional): New first name
        last_name (str, optional): New last name
        phone (str, optional): New phone number
        email (str, optional): New email address
        address (str, optional): New street address
        city (str, optional): New city
        state (str, optional): New state (2-letter code)
        zip_code (str, optional): New ZIP code
        emergency_contact_name (str, optional): New emergency contact name
        emergency_contact_phone (str, optional): New emergency contact phone
        practice_id (str): Practice ID (defaults to environment variable)
        
    Returns:
        dict: Updated patient information or error information
    """
    if not practice_id:
        practice_id = DEFAULT_PRACTICE_ID
        
    try:
        token = get_access_token()
        api_url = f"{BASE_URL}/v1/{practice_id}/patients/{patient_id}"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        # Build update data with only provided fields
        update_data = {}
        if first_name:
            update_data["firstname"] = first_name
        if last_name:
            update_data["lastname"] = last_name
        if phone:
            update_data["homephone"] = phone
        if email:
            update_data["email"] = email
        if address:
            update_data["address1"] = address
        if city:
            update_data["city"] = city
        if state:
            update_data["state"] = state
        if zip_code:
            update_data["zip"] = zip_code
        if emergency_contact_name:
            update_data["contactname"] = emergency_contact_name
        if emergency_contact_phone:
            update_data["contacthomephone"] = emergency_contact_phone
            
        if not update_data:
            raise ValueError("No update parameters provided")
        
        with httpx.Client(timeout=30.0) as client:
            response = client.put(api_url, headers=headers, data=update_data)
            
            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "patient": result,
                    "patient_id": patient_id,
                    "updates": update_data
                }
                
            elif response.status_code == 404:
                raise ValueError(f"Patient {patient_id} not found")
                
            elif response.status_code == 400:
                raise ValueError(f"Invalid patient update data: {response.text}")
                
            elif response.status_code == 401:
                global _access_token
                _access_token = None
                raise ValueError("Authentication failed")
                
            else:
                raise Exception(f"API Error: HTTP {response.status_code} - {response.text}")
                
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "patient_id": patient_id
        }

def test_connection():
    """
    Simple test to verify AthenaHealth API connectivity and authentication.
    """
    try:
        token = get_access_token()
        return {
            "success": True,
            "message": "Successfully connected to AthenaHealth API",
            "token_preview": f"{token[:20]}..." if token else None
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def cancel_appointment(appointment_id: str, practice_id: str = None, 
                      cancel_reason: str = None, cancel_note: str = None):
    """
    Cancels an existing appointment.
    
    Args:
        appointment_id (str): The appointment ID to cancel
        practice_id (str): Practice ID (defaults to environment variable)
        cancel_reason (str, optional): Reason for cancellation
        cancel_note (str, optional): Additional notes about cancellation
        
    Returns:
        dict: Cancellation result or error information
    """
    if not practice_id:
        practice_id = DEFAULT_PRACTICE_ID
        
    try:
        token = get_access_token()
        api_url = f"{BASE_URL}/v1/{practice_id}/appointments/{appointment_id}/cancel"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        cancel_data = {}
        if cancel_reason:
            cancel_data["cancelreason"] = cancel_reason
        if cancel_note:
            cancel_data["cancelnote"] = cancel_note
        
        with httpx.Client(timeout=30.0) as client:
            response = client.put(api_url, headers=headers, data=cancel_data)
            
            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "appointment_id": appointment_id,
                    "result": result
                }
                
            elif response.status_code == 404:
                raise ValueError(f"Appointment {appointment_id} not found")
                
            elif response.status_code == 400:
                raise ValueError(f"Cannot cancel appointment: {response.text}")
                
            elif response.status_code == 401:
                global _access_token
                _access_token = None
                raise ValueError("Authentication failed")
                
            else:
                raise Exception(f"API Error: HTTP {response.status_code} - {response.text}")
                
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "appointment_id": appointment_id
        }

def get_booked_appointments(department_id: str = None, provider_id: str = None,
                          start_date: str = None, end_date: str = None,
                          practice_id: str = None, limit: int = 50):
    """
    Retrieves list of booked appointments.
    
    Args:
        department_id (str, optional): Filter by department
        provider_id (str, optional): Filter by provider
        start_date (str, optional): Start date in MM/DD/YYYY format
        end_date (str, optional): End date in MM/DD/YYYY format
        practice_id (str): Practice ID (defaults to environment variable)
        limit (int): Maximum number of appointments to return
        
    Returns:
        dict: List of booked appointments or error information
    """
    if not practice_id:
        practice_id = DEFAULT_PRACTICE_ID
        
    try:
        token = get_access_token()
        api_url = f"{BASE_URL}/v1/{practice_id}/appointments/booked"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        params = {"limit": limit}
        if department_id:
            params["departmentid"] = department_id
        if provider_id:
            params["providerid"] = provider_id
        if start_date:
            params["startdate"] = start_date
        if end_date:
            params["enddate"] = end_date
        
        with httpx.Client(timeout=30.0) as client:
            response = client.get(api_url, headers=headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                appointments = data.get("appointments", [])
                return {
                    "success": True,
                    "appointments": appointments,
                    "count": len(appointments),
                    "filters": params
                }
                
            elif response.status_code == 401:
                global _access_token
                _access_token = None
                raise ValueError("Authentication failed")
                
            else:
                raise Exception(f"API Error: HTTP {response.status_code} - {response.text}")
                
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def get_patient_appointments(patient_id: str, start_date: str = None, 
                           end_date: str = None, practice_id: str = None):
    """
    Retrieves all appointments for a specific patient.
    
    Args:
        patient_id (str): The patient ID
        start_date (str, optional): Start date in MM/DD/YYYY format
        end_date (str, optional): End date in MM/DD/YYYY format
        practice_id (str): Practice ID (defaults to environment variable)
        
    Returns:
        dict: Patient's appointments or error information
    """
    if not practice_id:
        practice_id = DEFAULT_PRACTICE_ID
        
    try:
        token = get_access_token()
        api_url = f"{BASE_URL}/v1/{practice_id}/patients/{patient_id}/appointments"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        params = {}
        if start_date:
            params["startdate"] = start_date
        if end_date:
            params["enddate"] = end_date
        
        with httpx.Client(timeout=30.0) as client:
            response = client.get(api_url, headers=headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                appointments = data.get("appointments", [])
                return {
                    "success": True,
                    "patient_id": patient_id,
                    "appointments": appointments,
                    "count": len(appointments)
                }
                
            elif response.status_code == 404:
                raise ValueError(f"Patient {patient_id} not found")
                
            elif response.status_code == 401:
                global _access_token
                _access_token = None
                raise ValueError("Authentication failed")
                
            else:
                raise Exception(f"API Error: HTTP {response.status_code} - {response.text}")
                
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "patient_id": patient_id
        }

def get_all_providers(department_id: str = None, practice_id: str = None, limit: int = 100):
    """
    Retrieves list of all providers in the practice.
    
    Args:
        department_id (str, optional): Filter by department
        practice_id (str): Practice ID (defaults to environment variable)
        limit (int): Maximum number of providers to return
        
    Returns:
        dict: List of providers or error information
    """
    if not practice_id:
        practice_id = DEFAULT_PRACTICE_ID
        
    try:
        token = get_access_token()
        api_url = f"{BASE_URL}/v1/{practice_id}/providers"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        params = {"limit": limit}
        if department_id:
            params["departmentid"] = department_id
        
        with httpx.Client(timeout=30.0) as client:
            response = client.get(api_url, headers=headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                providers = data.get("providers", [])
                return {
                    "success": True,
                    "providers": providers,
                    "count": len(providers),
                    "department_id": department_id
                }
                
            elif response.status_code == 401:
                global _access_token
                _access_token = None
                raise ValueError("Authentication failed")
                
            else:
                raise Exception(f"API Error: HTTP {response.status_code} - {response.text}")
                
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def get_provider_details(provider_id: str, practice_id: str = None):
    """
    Retrieves detailed information about a specific provider.
    
    Args:
        provider_id (str): The provider ID
        practice_id (str): Practice ID (defaults to environment variable)
        
    Returns:
        dict: Provider details or error information
    """
    if not practice_id:
        practice_id = DEFAULT_PRACTICE_ID
        
    try:
        token = get_access_token()
        api_url = f"{BASE_URL}/v1/{practice_id}/providers/{provider_id}"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        with httpx.Client(timeout=30.0) as client:
            response = client.get(api_url, headers=headers)
            
            if response.status_code == 200:
                provider_data = response.json()
                return {
                    "success": True,
                    "provider": provider_data,
                    "provider_id": provider_id
                }
                
            elif response.status_code == 404:
                raise ValueError(f"Provider {provider_id} not found")
                
            elif response.status_code == 401:
                global _access_token
                _access_token = None
                raise ValueError("Authentication failed")
                
            else:
                raise Exception(f"API Error: HTTP {response.status_code} - {response.text}")
                
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "provider_id": provider_id
        }

def create_appointment_slot(department_id: str, provider_id: str, 
                          appointment_date: str, start_time: str, 
                          duration: int = 15, appointment_type_id: str = None,
                          practice_id: str = None):
    """
    Creates a new appointment slot.
    
    Args:
        department_id (str): The department ID
        provider_id (str): The provider ID
        appointment_date (str): Date in MM/DD/YYYY format
        start_time (str): Start time in HH:MM format (24-hour)
        duration (int): Duration in minutes (default 15)
        appointment_type_id (str, optional): Appointment type ID
        practice_id (str): Practice ID (defaults to environment variable)
        
    Returns:
        dict: Created appointment slot or error information
    """
    if not practice_id:
        practice_id = DEFAULT_PRACTICE_ID
        
    try:
        token = get_access_token()
        api_url = f"{BASE_URL}/v1/{practice_id}/appointments/open"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        slot_data = {
            "departmentid": department_id,
            "providerid": provider_id,
            "appointmentdate": appointment_date,
            "appointmenttime": start_time,
            "duration": duration
        }
        
        if appointment_type_id:
            slot_data["appointmenttypeid"] = appointment_type_id
        
        with httpx.Client(timeout=30.0) as client:
            response = client.post(api_url, headers=headers, data=slot_data)
            
            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "appointment_slot": result,
                    "department_id": department_id,
                    "provider_id": provider_id,
                    "appointment_date": appointment_date,
                    "start_time": start_time
                }
                
            elif response.status_code == 400:
                raise ValueError(f"Invalid slot data: {response.text}")
                
            elif response.status_code == 409:
                raise ValueError("Time slot conflicts with existing appointment")
                
            elif response.status_code == 401:
                global _access_token
                _access_token = None
                raise ValueError("Authentication failed")
                
            else:
                raise Exception(f"API Error: HTTP {response.status_code} - {response.text}")
                
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "department_id": department_id,
            "provider_id": provider_id,
            "appointment_date": appointment_date
        }

def verify_patient_insurance(patient_id: str, insurance_id: str = None, 
                           practice_id: str = None):
    """
    Verifies patient insurance eligibility and benefits.
    
    Args:
        patient_id (str): The patient ID
        insurance_id (str, optional): Specific insurance ID to verify
        practice_id (str): Practice ID (defaults to environment variable)
        
    Returns:
        dict: Insurance verification result or error information
    """
    if not practice_id:
        practice_id = DEFAULT_PRACTICE_ID
        
    try:
        token = get_access_token()
        api_url = f"{BASE_URL}/v1/{practice_id}/patients/{patient_id}/insurances/verify"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        verification_data = {}
        if insurance_id:
            verification_data["insuranceid"] = insurance_id
        
        with httpx.Client(timeout=30.0) as client:
            response = client.post(api_url, headers=headers, data=verification_data)
            
            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "patient_id": patient_id,
                    "verification_result": result,
                    "insurance_id": insurance_id
                }
                
            elif response.status_code == 404:
                raise ValueError(f"Patient {patient_id} or insurance not found")
                
            elif response.status_code == 400:
                raise ValueError(f"Invalid verification request: {response.text}")
                
            elif response.status_code == 401:
                global _access_token
                _access_token = None
                raise ValueError("Authentication failed")
                
            else:
                raise Exception(f"API Error: HTTP {response.status_code} - {response.text}")
                
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "patient_id": patient_id,
            "insurance_id": insurance_id
        }

def get_insurance_benefits(patient_id: str, insurance_id: str, 
                          service_type: str = None, practice_id: str = None):
    """
    Gets detailed insurance benefits information for a patient.
    
    Args:
        patient_id (str): The patient ID
        insurance_id (str): The insurance ID
        service_type (str, optional): Specific service type to check benefits for
        practice_id (str): Practice ID (defaults to environment variable)
        
    Returns:
        dict: Insurance benefits information or error information
    """
    if not practice_id:
        practice_id = DEFAULT_PRACTICE_ID
        
    try:
        token = get_access_token()
        api_url = f"{BASE_URL}/v1/{practice_id}/patients/{patient_id}/insurances/{insurance_id}/benefits"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        params = {}
        if service_type:
            params["servicetype"] = service_type
        
        with httpx.Client(timeout=30.0) as client:
            response = client.get(api_url, headers=headers, params=params)
            
            if response.status_code == 200:
                benefits_data = response.json()
                return {
                    "success": True,
                    "patient_id": patient_id,
                    "insurance_id": insurance_id,
                    "benefits": benefits_data,
                    "service_type": service_type
                }
                
            elif response.status_code == 404:
                raise ValueError(f"Benefits not found for patient {patient_id} and insurance {insurance_id}")
                
            elif response.status_code == 401:
                global _access_token
                _access_token = None
                raise ValueError("Authentication failed")
                
            else:
                raise Exception(f"API Error: HTTP {response.status_code} - {response.text}")
                
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "patient_id": patient_id,
            "insurance_id": insurance_id
        }

def create_appointment_reminder(appointment_id: str, reminder_type: str = "email",
                              reminder_time: int = 24, custom_message: str = None,
                              practice_id: str = None):
    """
    Creates an appointment reminder for a patient.
    
    Args:
        appointment_id (str): The appointment ID
        reminder_type (str): Type of reminder ("email", "sms", "phone", "portal")
        reminder_time (int): Hours before appointment to send reminder (default 24)
        custom_message (str, optional): Custom reminder message
        practice_id (str): Practice ID (defaults to environment variable)
        
    Returns:
        dict: Reminder creation result or error information
    """
    if not practice_id:
        practice_id = DEFAULT_PRACTICE_ID
        
    try:
        token = get_access_token()
        api_url = f"{BASE_URL}/v1/{practice_id}/appointments/{appointment_id}/reminders"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        reminder_data = {
            "remindertype": reminder_type,
            "remindertime": reminder_time
        }
        
        if custom_message:
            reminder_data["custommessage"] = custom_message
        
        with httpx.Client(timeout=30.0) as client:
            response = client.post(api_url, headers=headers, data=reminder_data)
            
            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "appointment_id": appointment_id,
                    "reminder": result,
                    "reminder_type": reminder_type,
                    "reminder_time": reminder_time
                }
                
            elif response.status_code == 404:
                raise ValueError(f"Appointment {appointment_id} not found")
                
            elif response.status_code == 400:
                raise ValueError(f"Invalid reminder data: {response.text}")
                
            elif response.status_code == 401:
                global _access_token
                _access_token = None
                raise ValueError("Authentication failed")
                
            else:
                raise Exception(f"API Error: HTTP {response.status_code} - {response.text}")
                
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "appointment_id": appointment_id
        }

def get_appointment_reminders(appointment_id: str = None, patient_id: str = None,
                            start_date: str = None, end_date: str = None,
                            practice_id: str = None, limit: int = 50):
    """
    Retrieves appointment reminders.
    
    Args:
        appointment_id (str, optional): Specific appointment ID
        patient_id (str, optional): Filter by patient ID
        start_date (str, optional): Start date in MM/DD/YYYY format
        end_date (str, optional): End date in MM/DD/YYYY format
        practice_id (str): Practice ID (defaults to environment variable)
        limit (int): Maximum number of reminders to return
        
    Returns:
        dict: List of appointment reminders or error information
    """
    if not practice_id:
        practice_id = DEFAULT_PRACTICE_ID
        
    try:
        token = get_access_token()
        
        if appointment_id:
            api_url = f"{BASE_URL}/v1/{practice_id}/appointments/{appointment_id}/reminders"
        else:
            api_url = f"{BASE_URL}/v1/{practice_id}/appointments/reminders"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        params = {"limit": limit}
        if patient_id:
            params["patientid"] = patient_id
        if start_date:
            params["startdate"] = start_date
        if end_date:
            params["enddate"] = end_date
        
        with httpx.Client(timeout=30.0) as client:
            response = client.get(api_url, headers=headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                reminders = data.get("reminders", [])
                return {
                    "success": True,
                    "reminders": reminders,
                    "count": len(reminders),
                    "appointment_id": appointment_id,
                    "patient_id": patient_id
                }
                
            elif response.status_code == 404:
                raise ValueError("Reminders not found")
                
            elif response.status_code == 401:
                global _access_token
                _access_token = None
                raise ValueError("Authentication failed")
                
            else:
                raise Exception(f"API Error: HTTP {response.status_code} - {response.text}")
                
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "appointment_id": appointment_id,
            "patient_id": patient_id
        }

def update_appointment_reminder(reminder_id: str, reminder_type: str = None,
                              reminder_time: int = None, custom_message: str = None,
                              is_active: bool = None, practice_id: str = None):
    """
    Updates an existing appointment reminder.
    
    Args:
        reminder_id (str): The reminder ID
        reminder_type (str, optional): New reminder type ("email", "sms", "phone", "portal")
        reminder_time (int, optional): New reminder time in hours before appointment
        custom_message (str, optional): New custom message
        is_active (bool, optional): Whether the reminder is active
        practice_id (str): Practice ID (defaults to environment variable)
        
    Returns:
        dict: Updated reminder or error information
    """
    if not practice_id:
        practice_id = DEFAULT_PRACTICE_ID
        
    try:
        token = get_access_token()
        api_url = f"{BASE_URL}/v1/{practice_id}/appointments/reminders/{reminder_id}"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        update_data = {}
        if reminder_type:
            update_data["remindertype"] = reminder_type
        if reminder_time is not None:
            update_data["remindertime"] = reminder_time
        if custom_message:
            update_data["custommessage"] = custom_message
        if is_active is not None:
            update_data["isactive"] = "true" if is_active else "false"
            
        if not update_data:
            raise ValueError("No update parameters provided")
        
        with httpx.Client(timeout=30.0) as client:
            response = client.put(api_url, headers=headers, data=update_data)
            
            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "reminder_id": reminder_id,
                    "reminder": result,
                    "updates": update_data
                }
                
            elif response.status_code == 404:
                raise ValueError(f"Reminder {reminder_id} not found")
                
            elif response.status_code == 400:
                raise ValueError(f"Invalid reminder update data: {response.text}")
                
            elif response.status_code == 401:
                global _access_token
                _access_token = None
                raise ValueError("Authentication failed")
                
            else:
                raise Exception(f"API Error: HTTP {response.status_code} - {response.text}")
                
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "reminder_id": reminder_id
        }

def delete_appointment_reminder(reminder_id: str, practice_id: str = None):
    """
    Deletes an appointment reminder.
    
    Args:
        reminder_id (str): The reminder ID
        practice_id (str): Practice ID (defaults to environment variable)
        
    Returns:
        dict: Deletion result or error information
    """
    if not practice_id:
        practice_id = DEFAULT_PRACTICE_ID
        
    try:
        token = get_access_token()
        api_url = f"{BASE_URL}/v1/{practice_id}/appointments/reminders/{reminder_id}"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        with httpx.Client(timeout=30.0) as client:
            response = client.delete(api_url, headers=headers)
            
            if response.status_code == 200:
                return {
                    "success": True,
                    "reminder_id": reminder_id,
                    "message": "Reminder deleted successfully"
                }
                
            elif response.status_code == 404:
                raise ValueError(f"Reminder {reminder_id} not found")
                
            elif response.status_code == 401:
                global _access_token
                _access_token = None
                raise ValueError("Authentication failed")
                
            else:
                raise Exception(f"API Error: HTTP {response.status_code} - {response.text}")
                
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "reminder_id": reminder_id
        }

def create_patient(first_name: str, last_name: str, phone: str, 
                  date_of_birth: str, department_id: str = "1", email: str = None, address: str = None,
                  city: str = None, state: str = None, zip_code: str = None,
                  emergency_contact_name: str = None, emergency_contact_phone: str = None,
                  practice_id: str = None):
    """
    Creates a new patient in AthenaHealth.
    
    Args:
        first_name (str): Patient's first name
        last_name (str): Patient's last name
        phone (str): Patient's phone number
        date_of_birth (str): Patient's date of birth (MM/DD/YYYY)
        department_id (str): Department ID (defaults to "1")
        email (str, optional): Patient's email address
        address (str, optional): Patient's street address
        city (str, optional): Patient's city
        state (str, optional): Patient's state
        zip_code (str, optional): Patient's zip code
        emergency_contact_name (str, optional): Emergency contact name
        emergency_contact_phone (str, optional): Emergency contact phone
        practice_id (str): Practice ID (defaults to environment variable)
        
    Returns:
        dict: Created patient information or error information
    """
    if not practice_id:
        practice_id = DEFAULT_PRACTICE_ID
        
    try:
        token = get_access_token()
        api_url = f"{BASE_URL}/v1/{practice_id}/patients"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        # Required fields
        patient_data = {
            "firstname": first_name,
            "lastname": last_name,
            "homephone": phone,
            "dob": date_of_birth,
            "departmentid": department_id
        }
        
        # Optional fields
        if email:
            patient_data["email"] = email
        if address:
            patient_data["address1"] = address
        if city:
            patient_data["city"] = city
        if state:
            patient_data["state"] = state
        if zip_code:
            patient_data["zip"] = zip_code
        if emergency_contact_name:
            patient_data["contactname"] = emergency_contact_name
        if emergency_contact_phone:
            patient_data["contactphone"] = emergency_contact_phone
        
        with httpx.Client(timeout=30.0) as client:
            response = client.post(api_url, headers=headers, data=patient_data)
            
            # Print the raw Athena API response for debugging
            print("ATHENA RAW RESPONSE STATUS:", response.status_code)
            print("ATHENA RAW RESPONSE TEXT:", response.text)
            
            if response.status_code == 200:
                result = response.json()
                if isinstance(result, list):
                    # If it's a list with one dict, use that dict
                    if len(result) == 1 and isinstance(result[0], dict):
                        result = result[0]
                    else:
                        return {
                            "success": False,
                            "error": "Athena API returned a list instead of a dict.",
                            "details": result,
                            "message": "Unexpected response format from Athena API during patient creation."
                        }
                patient_id = result.get("patientid")
                
                return {
                    "success": True,
                    "patient_id": patient_id,
                    "patient": result,
                    "message": f"Patient {first_name} {last_name} created successfully",
                    "patient_data": patient_data
                }
                
            elif response.status_code == 400:
                error_text = response.text
                if "duplicate" in error_text.lower() or "already exists" in error_text.lower():
                    return {
                        "success": False,
                        "error": "Patient already exists",
                        "error_type": "duplicate_patient",
                        "suggestion": "Try searching for the existing patient instead"
                    }
                else:
                    raise ValueError(f"Invalid patient data: {error_text}")
                
            elif response.status_code == 401:
                global _access_token
                _access_token = None
                raise ValueError("Authentication failed")
                
            else:
                raise Exception(f"API Error: HTTP {response.status_code} - {response.text}")
                
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "patient_data": {
                "first_name": first_name,
                "last_name": last_name,
                "phone": phone,
                "date_of_birth": date_of_birth
            }
        }

if __name__ == "__main__":
    """
    Simple connection test for AthenaHealth API client
    """
    print("🏥 AthenaHealth API Client")
    print("=" * 40)
    
    # Check environment configuration
    print("📋 Environment Configuration:")
    print(f"CLIENT_ID: {'✓ Set' if CLIENT_ID else '❌ Missing'}")
    print(f"CLIENT_SECRET: {'✓ Set' if CLIENT_SECRET else '❌ Missing'}")
    print(f"BASE_URL: {BASE_URL if BASE_URL else '❌ Missing'}")
    print(f"PRACTICE_ID: {DEFAULT_PRACTICE_ID if DEFAULT_PRACTICE_ID else '❌ Missing'}")
    
    if not (CLIENT_ID and CLIENT_SECRET and BASE_URL):
        print("\n❌ Missing required environment variables!")
        print("Please set: ATHENA_CLIENT_ID, ATHENA_CLIENT_SECRET, ATHENA_API_BASE_URL")
        exit(1)
    
    # Test connection
    print("\n🔗 Testing API connection...")
    result = test_connection()
    
    if result.get("success"):
        print("✅ Connection successful!")
        print(f"Token preview: {result.get('token_preview', 'N/A')}")
        print("\n🚀 AthenaHealth API client is ready for use!")
    else:
        print(f"❌ Connection failed: {result.get('error', 'Unknown error')}")
        print("\n🔧 Please check your configuration and try again.")
    
    print("\n" + "=" * 40)
    print("Available functions:")
    print("- search_patients()")
    print("- get_patient_details()")
    print("- get_patient_insurance()")
    print("- check_availability()")
    print("- book_appointment()")
    print("- create_appointment()")
    print("- update_appointment()")
    print("- cancel_appointment()")
    print("- get_appointment_types()")
    print("- get_all_providers()")
    print("- get_provider_details()")
    print("- get_booked_appointments()")
    print("- get_patient_appointments()")
    print("- And more...")
