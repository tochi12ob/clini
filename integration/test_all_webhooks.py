import requests
import logging
import json
from typing import Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_oauth2_token(auth: Dict[str, Any]) -> str:
    token_url = auth["token_url"]
    client_id = auth["client_id"]
    client_secret = auth["client_secret"]
    scope = auth.get("scope", "")
    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": scope,
    }
    resp = requests.post(token_url, data=data)
    resp.raise_for_status()
    return resp.json()["access_token"]

def build_dummy_payload(schema: Dict[str, Any]) -> Dict[str, Any]:
    payload = {}
    required = schema.get("required", [])
    properties = schema.get("properties", {})
    for field in required:
        ftype = properties.get(field, {}).get("type", "string")
        if ftype == "string":
            payload[field] = f"test_{field}"
        elif ftype == "integer":
            payload[field] = 1
        elif ftype == "boolean":
            payload[field] = True
        else:
            payload[field] = None
    return payload

def test_webhook(config: Dict[str, Any]):
    name = config["name"]
    api = config["api_schema"]
    url = api["url"]
    method = api["method"].upper()
    headers = api.get("request_headers", {}).copy()
    auth = api.get("auth_connection")
    body_schema = api.get("request_body_schema", {})
    payload = build_dummy_payload(body_schema)
    token = None
    if auth and auth.get("type") == "oauth2":
        try:
            token = get_oauth2_token(auth)
            headers["Authorization"] = f"Bearer {token}"
        except Exception as e:
            logger.error(f"[{name}] Failed to get OAuth2 token: {e}")
            return False, f"OAuth2 error: {e}"
    try:
        logger.info(f"Testing webhook: {name} -> {url}")
        resp = requests.request(method, url, headers=headers, json=payload, timeout=20)
        logger.info(f"[{name}] Status: {resp.status_code}, Response: {resp.text}")
        if resp.status_code >= 200 and resp.status_code < 300:
            return True, resp.text
        else:
            return False, resp.text
    except Exception as e:
        logger.error(f"[{name}] Request failed: {e}")
        return False, str(e)

def main():
    # Paste your configs JSON here or load from file
    configs_json = '''
{
  "configs": [
    {
      "name": "athena_string_get_access_token",
      "description": "Obtain an OAuth2 access token from AthenaHealth.",
      "type": "webhook",
      "response_timeout_secs": 20,
      "api_schema": {
        "url": "http://localhost:8000/api/tools/athena/string/get_access_token",
        "method": "POST",
        "path_params_schema": {},
        "query_params_schema": {
          "properties": {},
          "required": []
        },
        "request_body_schema": {
          "type": "object",
          "required": [],
          "properties": {}
        },
        "request_headers": {},
        "auth_connection": {
          "type": "oauth2",
          "token_url": "https://api.preview.platform.athenahealth.com/oauth2/v1/token",
          "client_id": "0oay0ra7o9QjMriHJ297",
          "client_secret": "-c8EYvTZtB-kUdEZCq1I_1ZYqFuuTwal626YM0W8C-QHKA-6nX2ngmPaJMrBfgfw",
          "scope": "athena/service/Athenanet.MDP.*",
          "practice_id": "195900"
        }
      },
      "dynamic_variables": {
        "dynamic_variable_placeholders": {}
      }
    },
    {
      "name": "athena_string_check_availability",
      "description": "Check open appointment slots.",
      "type": "webhook",
      "response_timeout_secs": 20,
      "api_schema": {
        "url": "http://localhost:8000/api/tools/athena/string/check_availability",
        "method": "POST",
        "path_params_schema": {},
        "query_params_schema": {
          "properties": {},
          "required": []
        },
        "request_body_schema": {
          "type": "object",
          "required": [
            "department_id",
            "start_date",
            "end_date"
          ],
          "properties": {
            "department_id": {
              "type": "string"
            },
            "start_date": {
              "type": "string"
            },
            "end_date": {
              "type": "string"
            },
            "reason_id": {
              "type": "integer"
            },
            "provider_id": {
              "type": "string"
            },
            "limit": {
              "type": "integer"
            }
          }
        },
        "request_headers": {},
        "auth_connection": {
          "type": "oauth2",
          "token_url": "https://api.preview.platform.athenahealth.com/oauth2/v1/token",
          "client_id": "0oay0ra7o9QjMriHJ297",
          "client_secret": "-c8EYvTZtB-kUdEZCq1I_1ZYqFuuTwal626YM0W8C-QHKA-6nX2ngmPaJMrBfgfw",
          "scope": "athena/service/Athenanet.MDP.*",
          "practice_id": "195900"
        }
      },
      "dynamic_variables": {
        "dynamic_variable_placeholders": {}
      }
    },
    {
      "name": "athena_string_get_patient_details",
      "description": "Get detailed information about a patient.",
      "type": "webhook",
      "response_timeout_secs": 20,
      "api_schema": {
        "url": "http://localhost:8000/api/tools/athena/string/get_patient_details",
        "method": "POST",
        "path_params_schema": {},
        "query_params_schema": {
          "properties": {},
          "required": []
        },
        "request_body_schema": {
          "type": "object",
          "required": [
            "patient_id"
          ],
          "properties": {
            "patient_id": {
              "type": "string"
            }
          }
        },
        "request_headers": {},
        "auth_connection": {
          "type": "oauth2",
          "token_url": "https://api.preview.platform.athenahealth.com/oauth2/v1/token",
          "client_id": "0oay0ra7o9QjMriHJ297",
          "client_secret": "-c8EYvTZtB-kUdEZCq1I_1ZYqFuuTwal626YM0W8C-QHKA-6nX2ngmPaJMrBfgfw",
          "scope": "athena/service/Athenanet.MDP.*",
          "practice_id": "195900"
        }
      },
      "dynamic_variables": {
        "dynamic_variable_placeholders": {}
      }
    },
    {
      "name": "athena_string_get_patient_insurance",
      "description": "Get insurance information for a patient.",
      "type": "webhook",
      "response_timeout_secs": 20,
      "api_schema": {
        "url": "http://localhost:8000/api/tools/athena/string/get_patient_insurance",
        "method": "POST",
        "path_params_schema": {},
        "query_params_schema": {
          "properties": {},
          "required": []
        },
        "request_body_schema": {
          "type": "object",
          "required": [
            "patient_id"
          ],
          "properties": {
            "patient_id": {
              "type": "string"
            }
          }
        },
        "request_headers": {},
        "auth_connection": {
          "type": "oauth2",
          "token_url": "https://api.preview.platform.athenahealth.com/oauth2/v1/token",
          "client_id": "0oay0ra7o9QjMriHJ297",
          "client_secret": "-c8EYvTZtB-kUdEZCq1I_1ZYqFuuTwal626YM0W8C-QHKA-6nX2ngmPaJMrBfgfw",
          "scope": "athena/service/Athenanet.MDP.*",
          "practice_id": "195900"
        }
      },
      "dynamic_variables": {
        "dynamic_variable_placeholders": {}
      }
    },
    {
      "name": "athena_string_get_patient_appointment_reasons",
      "description": "Get available appointment reasons for booking.",
      "type": "webhook",
      "response_timeout_secs": 20,
      "api_schema": {
        "url": "http://localhost:8000/api/tools/athena/string/get_patient_appointment_reasons",
        "method": "POST",
        "path_params_schema": {},
        "query_params_schema": {
          "properties": {},
          "required": []
        },
        "request_body_schema": {
          "type": "object",
          "required": [],
          "properties": {
            "department_id": {
              "type": "string"
            },
            "provider_id": {
              "type": "string"
            },
            "patient_type": {
              "type": "string"
            }
          }
        },
        "request_headers": {},
        "auth_connection": {
          "type": "oauth2",
          "token_url": "https://api.preview.platform.athenahealth.com/oauth2/v1/token",
          "client_id": "0oay0ra7o9QjMriHJ297",
          "client_secret": "-c8EYvTZtB-kUdEZCq1I_1ZYqFuuTwal626YM0W8C-QHKA-6nX2ngmPaJMrBfgfw",
          "scope": "athena/service/Athenanet.MDP.*",
          "practice_id": "195900"
        }
      },
      "dynamic_variables": {
        "dynamic_variable_placeholders": {}
      }
    },
    {
      "name": "athena_string_get_appointment_types",
      "description": "Get available appointment types for a department.",
      "type": "webhook",
      "response_timeout_secs": 20,
      "api_schema": {
        "url": "http://localhost:8000/api/tools/athena/string/get_appointment_types",
        "method": "POST",
        "path_params_schema": {},
        "query_params_schema": {
          "properties": {},
          "required": []
        },
        "request_body_schema": {
          "type": "object",
          "required": [
            "department_id"
          ],
          "properties": {
            "department_id": {
              "type": "string"
            }
          }
        },
        "request_headers": {},
        "auth_connection": {
          "type": "oauth2",
          "token_url": "https://api.preview.platform.athenahealth.com/oauth2/v1/token",
          "client_id": "0oay0ra7o9QjMriHJ297",
          "client_secret": "-c8EYvTZtB-kUdEZCq1I_1ZYqFuuTwal626YM0W8C-QHKA-6nX2ngmPaJMrBfgfw",
          "scope": "athena/service/Athenanet.MDP.*",
          "practice_id": "195900"
        }
      },
      "dynamic_variables": {
        "dynamic_variable_placeholders": {}
      }
    },
    {
      "name": "athena_string_book_appointment",
      "description": "Book an appointment for a patient.",
      "type": "webhook",
      "response_timeout_secs": 20,
      "api_schema": {
        "url": "http://localhost:8000/api/tools/athena/string/book_appointment",
        "method": "POST",
        "path_params_schema": {},
        "query_params_schema": {
          "properties": {},
          "required": []
        },
        "request_body_schema": {
          "type": "object",
          "required": [
            "appointment_id",
            "patient_id"
          ],
          "properties": {
            "appointment_id": {
              "type": "string"
            },
            "patient_id": {
              "type": "string"
            },
            "reason": {
              "type": "string"
            },
            "insurance_id": {
              "type": "string"
            },
            "appointment_type_id": {
              "type": "string"
            },
            "reason_id": {
              "type": "integer"
            }
          }
        },
        "request_headers": {},
        "auth_connection": {
          "type": "oauth2",
          "token_url": "https://api.preview.platform.athenahealth.com/oauth2/v1/token",
          "client_id": "0oay0ra7o9QjMriHJ297",
          "client_secret": "-c8EYvTZtB-kUdEZCq1I_1ZYqFuuTwal626YM0W8C-QHKA-6nX2ngmPaJMrBfgfw",
          "scope": "athena/service/Athenanet.MDP.*",
          "practice_id": "195900"
        }
      },
      "dynamic_variables": {
        "dynamic_variable_placeholders": {}
      }
    },
    {
      "name": "athena_string_create_appointment",
      "description": "Create a new appointment.",
      "type": "webhook",
      "response_timeout_secs": 20,
      "api_schema": {
        "url": "http://localhost:8000/api/tools/athena/string/create_appointment",
        "method": "POST",
        "path_params_schema": {},
        "query_params_schema": {
          "properties": {},
          "required": []
        },
        "request_body_schema": {
          "type": "object",
          "required": [
            "patient_id",
            "department_id",
            "appointment_date"
          ],
          "properties": {
            "patient_id": {
              "type": "string"
            },
            "department_id": {
              "type": "string"
            },
            "appointment_date": {
              "type": "string"
            },
            "appointment_time": {
              "type": "string"
            },
            "appointment_type_id": {
              "type": "string"
            },
            "provider_id": {
              "type": "string"
            },
            "reason": {
              "type": "string"
            }
          }
        },
        "request_headers": {},
        "auth_connection": {
          "type": "oauth2",
          "token_url": "https://api.preview.platform.athenahealth.com/oauth2/v1/token",
          "client_id": "0oay0ra7o9QjMriHJ297",
          "client_secret": "-c8EYvTZtB-kUdEZCq1I_1ZYqFuuTwal626YM0W8C-QHKA-6nX2ngmPaJMrBfgfw",
          "scope": "athena/service/Athenanet.MDP.*",
          "practice_id": "195900"
        }
      },
      "dynamic_variables": {
        "dynamic_variable_placeholders": {}
      }
    },
    {
      "name": "athena_string_get_all_providers",
      "description": "Get all providers in the practice.",
      "type": "webhook",
      "response_timeout_secs": 20,
      "api_schema": {
        "url": "http://localhost:8000/api/tools/athena/string/get_all_providers",
        "method": "POST",
        "path_params_schema": {},
        "query_params_schema": {
          "properties": {},
          "required": []
        },
        "request_body_schema": {
          "type": "object",
          "required": [],
          "properties": {
            "department_id": {
              "type": "string"
            },
            "limit": {
              "type": "integer"
            }
          }
        },
        "request_headers": {},
        "auth_connection": {
          "type": "oauth2",
          "token_url": "https://api.preview.platform.athenahealth.com/oauth2/v1/token",
          "client_id": "0oay0ra7o9QjMriHJ297",
          "client_secret": "-c8EYvTZtB-kUdEZCq1I_1ZYqFuuTwal626YM0W8C-QHKA-6nX2ngmPaJMrBfgfw",
          "scope": "athena/service/Athenanet.MDP.*",
          "practice_id": "195900"
        }
      },
      "dynamic_variables": {
        "dynamic_variable_placeholders": {}
      }
    },
    {
      "name": "athena_string_get_provider_details",
      "description": "Get detailed information about a specific provider.",
      "type": "webhook",
      "response_timeout_secs": 20,
      "api_schema": {
        "url": "http://localhost:8000/api/tools/athena/string/get_provider_details",
        "method": "POST",
        "path_params_schema": {},
        "query_params_schema": {
          "properties": {},
          "required": []
        },
        "request_body_schema": {
          "type": "object",
          "required": [
            "provider_id"
          ],
          "properties": {
            "provider_id": {
              "type": "string"
            }
          }
        },
        "request_headers": {},
        "auth_connection": {
          "type": "oauth2",
          "token_url": "https://api.preview.platform.athenahealth.com/oauth2/v1/token",
          "client_id": "0oay0ra7o9QjMriHJ297",
          "client_secret": "-c8EYvTZtB-kUdEZCq1I_1ZYqFuuTwal626YM0W8C-QHKA-6nX2ngmPaJMrBfgfw",
          "scope": "athena/service/Athenanet.MDP.*",
          "practice_id": "195900"
        }
      },
      "dynamic_variables": {
        "dynamic_variable_placeholders": {}
      }
    },
    {
      "name": "athena_string_search_patients",
      "description": "Search for patients by various criteria.",
      "type": "webhook",
      "response_timeout_secs": 20,
      "api_schema": {
        "url": "http://localhost:8000/api/tools/athena/string/search_patients",
        "method": "POST",
        "path_params_schema": {},
        "query_params_schema": {
          "properties": {},
          "required": []
        },
        "request_body_schema": {
          "type": "object",
          "required": [],
          "properties": {
            "first_name": {
              "type": "string"
            },
            "last_name": {
              "type": "string"
            },
            "date_of_birth": {
              "type": "string"
            },
            "phone": {
              "type": "string"
            },
            "limit": {
              "type": "integer"
            }
          }
        },
        "request_headers": {},
        "auth_connection": {
          "type": "oauth2",
          "token_url": "https://api.preview.platform.athenahealth.com/oauth2/v1/token",
          "client_id": "0oay0ra7o9QjMriHJ297",
          "client_secret": "-c8EYvTZtB-kUdEZCq1I_1ZYqFuuTwal626YM0W8C-QHKA-6nX2ngmPaJMrBfgfw",
          "scope": "athena/service/Athenanet.MDP.*",
          "practice_id": "195900"
        }
      },
      "dynamic_variables": {
        "dynamic_variable_placeholders": {}
      }
    },
    {
      "name": "athena_string_update_patient",
      "description": "Update patient information.",
      "type": "webhook",
      "response_timeout_secs": 20,
      "api_schema": {
        "url": "http://localhost:8000/api/tools/athena/string/update_patient",
        "method": "POST",
        "path_params_schema": {},
        "query_params_schema": {
          "properties": {},
          "required": []
        },
        "request_body_schema": {
          "type": "object",
          "required": [
            "patient_id"
          ],
          "properties": {
            "patient_id": {
              "type": "string"
            },
            "first_name": {
              "type": "string"
            },
            "last_name": {
              "type": "string"
            },
            "phone": {
              "type": "string"
            },
            "email": {
              "type": "string"
            },
            "address": {
              "type": "string"
            },
            "city": {
              "type": "string"
            },
            "state": {
              "type": "string"
            },
            "zip_code": {
              "type": "string"
            },
            "emergency_contact_name": {
              "type": "string"
            },
            "emergency_contact_phone": {
              "type": "string"
            }
          }
        },
        "request_headers": {},
        "auth_connection": {
          "type": "oauth2",
          "token_url": "https://api.preview.platform.athenahealth.com/oauth2/v1/token",
          "client_id": "0oay0ra7o9QjMriHJ297",
          "client_secret": "-c8EYvTZtB-kUdEZCq1I_1ZYqFuuTwal626YM0W8C-QHKA-6nX2ngmPaJMrBfgfw",
          "scope": "athena/service/Athenanet.MDP.*",
          "practice_id": "195900"
        }
      },
      "dynamic_variables": {
        "dynamic_variable_placeholders": {}
      }
    },
    {
      "name": "athena_string_cancel_appointment",
      "description": "Cancel an appointment.",
      "type": "webhook",
      "response_timeout_secs": 20,
      "api_schema": {
        "url": "http://localhost:8000/api/tools/athena/string/cancel_appointment",
        "method": "POST",
        "path_params_schema": {},
        "query_params_schema": {
          "properties": {},
          "required": []
        },
        "request_body_schema": {
          "type": "object",
          "required": [
            "appointment_id"
          ],
          "properties": {
            "appointment_id": {
              "type": "string"
            },
            "cancel_reason": {
              "type": "string"
            },
            "cancel_note": {
              "type": "string"
            }
          }
        },
        "request_headers": {},
        "auth_connection": {
          "type": "oauth2",
          "token_url": "https://api.preview.platform.athenahealth.com/oauth2/v1/token",
          "client_id": "0oay0ra7o9QjMriHJ297",
          "client_secret": "-c8EYvTZtB-kUdEZCq1I_1ZYqFuuTwal626YM0W8C-QHKA-6nX2ngmPaJMrBfgfw",
          "scope": "athena/service/Athenanet.MDP.*",
          "practice_id": "195900"
        }
      },
      "dynamic_variables": {
        "dynamic_variable_placeholders": {}
      }
    },
    {
      "name": "athena_string_get_booked_appointments",
      "description": "Get all booked appointments.",
      "type": "webhook",
      "response_timeout_secs": 20,
      "api_schema": {
        "url": "http://localhost:8000/api/tools/athena/string/get_booked_appointments",
        "method": "POST",
        "path_params_schema": {},
        "query_params_schema": {
          "properties": {},
          "required": []
        },
        "request_body_schema": {
          "type": "object",
          "required": [],
          "properties": {
            "department_id": {
              "type": "string"
            },
            "provider_id": {
              "type": "string"
            },
            "start_date": {
              "type": "string"
            },
            "end_date": {
              "type": "string"
            },
            "limit": {
              "type": "integer"
            }
          }
        },
        "request_headers": {},
        "auth_connection": {
          "type": "oauth2",
          "token_url": "https://api.preview.platform.athenahealth.com/oauth2/v1/token",
          "client_id": "0oay0ra7o9QjMriHJ297",
          "client_secret": "-c8EYvTZtB-kUdEZCq1I_1ZYqFuuTwal626YM0W8C-QHKA-6nX2ngmPaJMrBfgfw",
          "scope": "athena/service/Athenanet.MDP.*",
          "practice_id": "195900"
        }
      },
      "dynamic_variables": {
        "dynamic_variable_placeholders": {}
      }
    },
    {
      "name": "athena_string_get_patient_appointments",
      "description": "Get all appointments for a specific patient.",
      "type": "webhook",
      "response_timeout_secs": 20,
      "api_schema": {
        "url": "http://localhost:8000/api/tools/athena/string/get_patient_appointments",
        "method": "POST",
        "path_params_schema": {},
        "query_params_schema": {
          "properties": {},
          "required": []
        },
        "request_body_schema": {
          "type": "object",
          "required": [
            "patient_id"
          ],
          "properties": {
            "patient_id": {
              "type": "string"
            },
            "start_date": {
              "type": "string"
            },
            "end_date": {
              "type": "string"
            }
          }
        },
        "request_headers": {},
        "auth_connection": {
          "type": "oauth2",
          "token_url": "https://api.preview.platform.athenahealth.com/oauth2/v1/token",
          "client_id": "0oay0ra7o9QjMriHJ297",
          "client_secret": "-c8EYvTZtB-kUdEZCq1I_1ZYqFuuTwal626YM0W8C-QHKA-6nX2ngmPaJMrBfgfw",
          "scope": "athena/service/Athenanet.MDP.*",
          "practice_id": "195900"
        }
      },
      "dynamic_variables": {
        "dynamic_variable_placeholders": {}
      }
    },
    {
      "name": "athena_string_create_patient",
      "description": "Create a new patient in AthenaHealth.",
      "type": "webhook",
      "response_timeout_secs": 20,
      "api_schema": {
        "url": "http://localhost:8000/api/tools/athena/string/create_patient",
        "method": "POST",
        "path_params_schema": {},
        "query_params_schema": {
          "properties": {},
          "required": []
        },
        "request_body_schema": {
          "type": "object",
          "required": [
            "first_name",
            "last_name",
            "phone",
            "date_of_birth",
            "department_id"
          ],
          "properties": {
            "first_name": {
              "type": "string"
            },
            "last_name": {
              "type": "string"
            },
            "phone": {
              "type": "string"
            },
            "date_of_birth": {
              "type": "string"
            },
            "department_id": {
              "type": "string"
            },
            "email": {
              "type": "string"
            },
            "address": {
              "type": "string"
            },
            "city": {
              "type": "string"
            },
            "state": {
              "type": "string"
            },
            "zip_code": {
              "type": "string"
            },
            "emergency_contact_name": {
              "type": "string"
            },
            "emergency_contact_phone": {
              "type": "string"
            }
          }
        },
        "request_headers": {},
        "auth_connection": {
          "type": "oauth2",
          "token_url": "https://api.preview.platform.athenahealth.com/oauth2/v1/token",
          "client_id": "0oay0ra7o9QjMriHJ297",
          "client_secret": "-c8EYvTZtB-kUdEZCq1I_1ZYqFuuTwal626YM0W8C-QHKA-6nX2ngmPaJMrBfgfw",
          "scope": "athena/service/Athenanet.MDP.*",
          "practice_id": "195900"
        }
      },
      "dynamic_variables": {
        "dynamic_variable_placeholders": {}
      }
    }
  ]
}
    '''
    configs = json.loads(configs_json)["configs"]
    results = []
    for config in configs:
        success, info = test_webhook(config)
        results.append((config["name"], success, info))
    print("\n=== Webhook Test Results ===")
    for name, success, info in results:
        print(f"{name}: {'SUCCESS' if success else 'FAIL'}\n  Info: {info[:200]}")

if __name__ == "__main__":
    main() 