import os
import requests
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_KEY = os.getenv("ELEVENLABS_API_KEY")
BASE_URL = "https://api.elevenlabs.io/v1/convai/tools"
YOUR_DOMAIN = os.getenv("PUBLIC_API_DOMAIN", "https://f1edba4bce1e.ngrok-free.app")

if not API_KEY:
    logger.error("ELEVENLABS_API_KEY not found in environment variables.")
    exit(1)

headers = {
    "Accept": "application/json",
    "xi-api-key": API_KEY,
    "Content-Type": "application/json"
}

base_tools_url = f"{YOUR_DOMAIN}/api/tools"

tools = [
    {
        "name": "check_availability",
        "description": "Check appointment availability for a clinic (Epic or Athena).",
        "url": f"{base_tools_url}/check-availability",
        "method": "POST",
        "request_body_schema": {
            "type": "object",
            "required": ["department_id", "date"],
            "properties": {
                "department_id": {"type": "string", "description": "Department ID"},
                "date": {"type": "string", "description": "Date to check (MM/DD/YYYY or natural language)"},
                "provider": {"type": "string", "description": "EHR provider: 'epic' or 'athena'", "default": "athena"}
            }
        }
    },
    {
        "name": "book_appointment",
        "description": "Book an appointment for a patient (Epic or Athena).",
        "url": f"{base_tools_url}/book-appointment",
        "method": "POST",
        "request_body_schema": {
            "type": "object",
            "required": ["patient_name", "date", "time"],
            "properties": {
                "patient_name": {"type": "string", "description": "Full name of the patient"},
                "date": {"type": "string", "description": "Date of appointment"},
                "time": {"type": "string", "description": "Time of appointment"},
                "provider": {"type": "string", "description": "EHR provider: 'epic' or 'athena'", "default": "athena"}
            }
        }
    },
    {
        "name": "pre_check_patient",
        "description": "Pre-check if a patient exists before scheduling (Epic or Athena).",
        "url": f"{base_tools_url}/pre-check-patient",
        "method": "POST",
        "request_body_schema": {
            "type": "object",
            "required": ["patient_name", "patient_phone"],
            "properties": {
                "patient_name": {"type": "string", "description": "Full name of the patient"},
                "patient_phone": {"type": "string", "description": "Patient's phone number"},
                "provider": {"type": "string", "description": "EHR provider: 'epic' or 'athena'", "default": "athena"}
            }
        }
    },
    {
        "name": "register_patient",
        "description": "Register a new patient (Epic or Athena).",
        "url": f"{base_tools_url}/register-patient",
        "method": "POST",
        "request_body_schema": {
            "type": "object",
            "required": ["patient_name", "patient_phone"],
            "properties": {
                "patient_name": {"type": "string", "description": "Full name of the patient"},
                "patient_phone": {"type": "string", "description": "Patient's phone number"},
                "date_of_birth": {"type": "string", "description": "Date of birth"},
                "email": {"type": "string", "description": "Email address"},
                "provider": {"type": "string", "description": "EHR provider: 'epic' or 'athena'", "default": "athena"}
            }
        }
    },
    {
        "name": "verify_patient",
        "description": "Verify patient identity (Epic or Athena).",
        "url": f"{base_tools_url}/verify-patient",
        "method": "POST",
        "request_body_schema": {
            "type": "object",
            "required": ["patient_name", "patient_phone", "date_of_birth"],
            "properties": {
                "patient_name": {"type": "string", "description": "Full name of the patient"},
                "patient_phone": {"type": "string", "description": "Patient's phone number"},
                "date_of_birth": {"type": "string", "description": "Date of birth"},
                "provider": {"type": "string", "description": "EHR provider: 'epic' or 'athena'", "default": "athena"}
            }
        }
    },
    {
        "name": "epic_search_patients",
        "description": "Search for patients in Epic EHR.",
        "url": f"{base_tools_url}/epic/search-patients",
        "method": "POST",
        "request_body_schema": {
            "type": "object",
            "required": ["first_name", "last_name"],
            "properties": {
                "first_name": {"type": "string", "description": "Patient's first name"},
                "last_name": {"type": "string", "description": "Patient's last name"},
                "date_of_birth": {"type": "string", "description": "Date of birth"},
                "phone": {"type": "string", "description": "Phone number"},
                "identifier": {"type": "string", "description": "Patient identifier"}
            }
        }
    },
    {
        "name": "epic_search_providers",
        "description": "Search for providers in Epic EHR.",
        "url": f"{base_tools_url}/epic/search-providers",
        "method": "POST",
        "request_body_schema": {
            "type": "object",
            "required": [],
            "properties": {
                "name": {"type": "string", "description": "Provider's name"},
                "specialty": {"type": "string", "description": "Specialty"},
                "location_id": {"type": "string", "description": "Location ID"}
            }
        }
    },
    {
        "name": "epic_test_connection",
        "description": "Test Epic FHIR API connection.",
        "url": f"{base_tools_url}/epic/test-connection",
        "method": "GET",
        "request_body_schema": None
    }
]

def register_tool(tool):
    api_schema = {
        "url": tool["url"],
        "method": tool["method"],
        "path_params_schema": {},
        "query_params_schema": {
            "properties": {},
            "required": []
        },
        "request_body_schema": tool["request_body_schema"],
        "request_headers": {},
        "auth_connection": None
    }
    payload = {
        "tool_config": {
            "name": tool["name"],
            "description": tool["description"],
            "response_timeout_secs": 20,
            "type": "webhook",
            "api_schema": api_schema,
            "dynamic_variables": {"dynamic_variable_placeholders": {}}
        }
    }
    try:
        response = requests.post(BASE_URL, headers=headers, json=payload)
        if response.status_code in [200, 201]:
            logger.info(f"Successfully registered tool: {tool['name']}")
        else:
            logger.error(f"Failed to register tool {tool['name']}. Status: {response.status_code}, Response: {response.text}")
    except Exception as e:
        logger.error(f"Exception registering tool {tool['name']}: {str(e)}")

if __name__ == "__main__":
    for tool in tools:
        register_tool(tool)
    logger.info("Tool registration complete.") 