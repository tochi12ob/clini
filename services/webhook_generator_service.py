import os
from typing import List, Dict, Any, Optional
import requests

class WebhookGeneratorService:
    """
    Service to generate webhook tool configurations for Epic, AthenaHealth, or both.
    Returns ElevenLabs-compatible webhook tool schemas.
    """
    def __init__(self, public_api_domain: Optional[str] = None):
        self.public_api_domain = public_api_domain or self._get_ngrok_url() or os.getenv("PUBLIC_API_DOMAIN", "https://your-domain.com")

    def _get_ngrok_url(self) -> Optional[str]:
        """Try to get the public ngrok URL if ngrok is running locally, or use the provided one."""
        # Always use the provided ngrok URL if set
        forced_ngrok_url = os.getenv("FORCED_NGROK_URL", "https://b561215328df.ngrok-free.app ")
        if forced_ngrok_url:
            return forced_ngrok_url
        try:
            resp = requests.get("http://127.0.0.1:4040/api/tunnels", timeout=1)
            if resp.status_code == 200:
                tunnels = resp.json().get("tunnels", [])
                for tunnel in tunnels:
                    public_url = tunnel.get("public_url")
                    if public_url and public_url.startswith("https://"):
                        return public_url
                # fallback to http if no https tunnel
                for tunnel in tunnels:
                    public_url = tunnel.get("public_url")
                    if public_url and public_url.startswith("http://"):
                        return public_url
        except Exception:
            pass
        return None

    def generate_webhook_config(self, clinic_id: str, ehr: str, epic_creds: Optional[dict] = None, athena_creds: Optional[dict] = None) -> List[Dict[str, Any]]:
        """
        Generate webhook tool config(s) for the specified EHR(s).
        ehr: 'epic', 'athena', or 'both'
        epic_creds: dict with keys epic_client_id, epic_client_secret, epic_fhir_base_url, epic_redirect_uri (optional)
        athena_creds: dict with keys athena_client_id, athena_client_secret, athena_api_base_url, athena_practice_id
        Returns a list of tool configs (dicts)
        """
        configs = []
        if ehr in ("epic", "both"):
            if not epic_creds or not all(k in epic_creds for k in ("epic_client_id", "epic_client_secret", "epic_fhir_base_url")):
                raise ValueError("Epic credentials required for Epic webhook generation.")
            configs.append(self._epic_config(clinic_id, epic_creds))
        if ehr in ("athena", "both"):
            if not athena_creds or not all(k in athena_creds for k in ("athena_client_id", "athena_client_secret", "athena_api_base_url", "athena_practice_id")):
                raise ValueError("Athena credentials required for Athena webhook generation.")
            configs.extend(self._athena_function_webhooks(clinic_id, athena_creds))
        return configs

    def _epic_config(self, clinic_id: str, epic_creds: dict) -> Dict[str, Any]:
        base_url = epic_creds["epic_fhir_base_url"]
        redirect_uri = epic_creds.get("epic_redirect_uri", "http://localhost:8000/callback")
        return {
            "name": f"epic_{clinic_id}_webhook",
            "description": f"Webhook for Epic FHIR integration for clinic {clinic_id}",
            "type": "webhook",
            "response_timeout_secs": 20,
            "api_schema": {
                "url": f"{self.public_api_domain}/api/tools/epic/{clinic_id}/webhook",
                "method": "POST",
                "path_params_schema": {},
                "query_params_schema": {"properties": {}, "required": []},
                "request_body_schema": {
                    "type": "object",
                    "required": ["resource", "action"],
                    "properties": {
                        "resource": {"type": "string", "description": "FHIR resource type (e.g., Patient, Appointment)"},
                        "action": {"type": "string", "description": "Action to perform (e.g., search, book)"},
                        "parameters": {"type": "object", "description": "Parameters for the FHIR action"}
                    }
                },
                "request_headers": {},
                "auth_connection": {
                    "type": "oauth2",
                    "token_url": f"{base_url}/oauth2/token",
                    "client_id": epic_creds["epic_client_id"],
                    "client_secret": epic_creds["epic_client_secret"],
                    "scope": "system/Patient.read",
                    "redirect_uri": redirect_uri
                }
            },
            "dynamic_variables": {"dynamic_variable_placeholders": {}}
        }

    def _athena_function_webhooks(self, clinic_id: str, athena_creds: dict) -> List[Dict[str, Any]]:
        base_url = athena_creds["athena_api_base_url"]
        practice_id = athena_creds["athena_practice_id"]
        auth_connection = {
            "type": "oauth2",
            "token_url": f"{base_url}/oauth2/v1/token",
            "client_id": athena_creds["athena_client_id"],
            "client_secret": athena_creds["athena_client_secret"],
            "scope": "athena/service/Athenanet.MDP.*",
            "practice_id": practice_id
        }
        # List of Athena functions and their parameter schemas
        athena_functions = [
            {
                "func": "get_access_token",
                "description": "Obtain an OAuth2 access token from AthenaHealth.",
                "params": {}
            },
            {
                "func": "check_availability",
                "description": "Check open appointment slots.",
                "params": {
                    "department_id": {"type": "string"},
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                    "reason_id": {"type": "integer", "default": -1},
                    "provider_id": {"type": "string", "default": None},
                    "limit": {"type": "integer", "default": 10}
                },
                "required": ["department_id", "start_date", "end_date"]
            },
            {
                "func": "get_patient_details",
                "description": "Get detailed information about a patient.",
                "params": {
                    "patient_id": {"type": "string"}
                },
                "required": ["patient_id"]
            },
            {
                "func": "get_patient_insurance",
                "description": "Get insurance information for a patient.",
                "params": {
                    "patient_id": {"type": "string"}
                },
                "required": ["patient_id"]
            },
            {
                "func": "get_patient_appointment_reasons",
                "description": "Get available appointment reasons for booking.",
                "params": {
                    "department_id": {"type": "string", "default": None},
                    "provider_id": {"type": "string", "default": None},
                    "patient_type": {"type": "string", "default": None}
                },
                "required": []
            },
            {
                "func": "get_appointment_types",
                "description": "Get available appointment types for a department.",
                "params": {
                    "department_id": {"type": "string"}
                },
                "required": ["department_id"]
            },
            {
                "func": "book_appointment",
                "description": "Book an appointment for a patient.",
                "params": {
                    "appointment_id": {"type": "string"},
                    "patient_id": {"type": "string"},
                    "reason": {"type": "string", "default": None},
                    "insurance_id": {"type": "string", "default": None},
                    "appointment_type_id": {"type": "string", "default": None},
                    "reason_id": {"type": "integer", "default": None}
                },
                "required": ["appointment_id", "patient_id"]
            },
            {
                "func": "create_appointment",
                "description": "Create a new appointment.",
                "params": {
                    "patient_id": {"type": "string"},
                    "department_id": {"type": "string"},
                    "appointment_date": {"type": "string"},
                    "appointment_time": {"type": "string", "default": None},
                    "appointment_type_id": {"type": "string", "default": None},
                    "provider_id": {"type": "string", "default": None},
                    "reason": {"type": "string", "default": None}
                },
                "required": ["patient_id", "department_id", "appointment_date"]
            },
            {
                "func": "get_all_providers",
                "description": "Get all providers in the practice.",
                "params": {
                    "department_id": {"type": "string"},
                    "limit": {"type": "integer"}
                },
                "required": []
            },
            {
                "func": "get_provider_details",
                "description": "Get detailed information about a specific provider.",
                "params": {
                    "provider_id": {"type": "string"}
                },
                "required": ["provider_id"]
            },
            {
                "func": "search_patients",
                "description": "Search for patients by various criteria.",
                "params": {
                    "first_name": {"type": "string"},
                    "last_name": {"type": "string"},
                    "date_of_birth": {"type": "string"},
                    "phone": {"type": "string"},
                    "limit": {"type": "integer"}
                },
                "required": []
            },
            {
                "func": "update_patient",
                "description": "Update patient information.",
                "params": {
                    "patient_id": {"type": "string"},
                    "first_name": {"type": "string"},
                    "last_name": {"type": "string"},
                    "phone": {"type": "string"},
                    "email": {"type": "string"},
                    "address": {"type": "string"},
                    "city": {"type": "string"},
                    "state": {"type": "string"},
                    "zip_code": {"type": "string"},
                    "emergency_contact_name": {"type": "string"},
                    "emergency_contact_phone": {"type": "string"}
                },
                "required": ["patient_id"]
            },
            {
                "func": "cancel_appointment",
                "description": "Cancel an appointment.",
                "params": {
                    "appointment_id": {"type": "string"},
                    "cancel_reason": {"type": "string"},
                    "cancel_note": {"type": "string"}
                },
                "required": ["appointment_id"]
            },
            {
                "func": "get_booked_appointments",
                "description": "Get all booked appointments.",
                "params": {
                    "department_id": {"type": "string"},
                    "provider_id": {"type": "string"},
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                    "limit": {"type": "integer"}
                },
                "required": []
            },
            {
                "func": "get_patient_appointments",
                "description": "Get all appointments for a specific patient.",
                "params": {
                    "patient_id": {"type": "string"},
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"}
                },
                "required": ["patient_id"]
            },
            {
                "func": "create_patient",
                "description": "Create a new patient in AthenaHealth.",
                "params": {
                    "first_name": {"type": "string"},
                    "last_name": {"type": "string"},
                    "phone": {"type": "string"},
                    "date_of_birth": {"type": "string"},
                    "department_id": {"type": "string"},
                    "email": {"type": "string"},
                    "address": {"type": "string"},
                    "city": {"type": "string"},
                    "state": {"type": "string"},
                    "zip_code": {"type": "string"},
                    "emergency_contact_name": {"type": "string"},
                    "emergency_contact_phone": {"type": "string"}
                },
                "required": ["first_name", "last_name", "phone", "date_of_birth", "department_id"]
            },
            # Add more as needed for full coverage
        ]
        webhooks = []
        for fn in athena_functions:
            fn_name = fn["func"]
            url = f"{self.public_api_domain}/api/tools/athena/{clinic_id}/{fn_name}"
            params = fn.get("params", {})
            required = fn.get("required", list(params.keys()))
            properties = {k: {"type": v["type"]} for k, v in params.items()}
            webhook = {
                "name": f"athena_{clinic_id}_{fn_name}",
                "description": fn["description"],
                "type": "webhook",
                "response_timeout_secs": 20,
                "api_schema": {
                    "url": url,
                    "method": "POST",
                    "path_params_schema": {},
                    "query_params_schema": {"properties": {}, "required": []},
                    "request_body_schema": {
                        "type": "object",
                        "required": required,
                        "properties": properties
                    },
                    "request_headers": {},
                    "auth_connection": auth_connection
                },
                "dynamic_variables": {"dynamic_variable_placeholders": {}}
            }
            webhooks.append(webhook)
        return webhooks 