import os
import logging
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def set_epic_env_vars():
    os.environ["EPIC_CLIENT_ID"] = "4d7932be-77db-4812-9357-a8d6c479865b"
    os.environ["EPIC_CLIENT_SECRET"] = "MskWdNLgRqiUFiro6OkvXGZryDXt4EbGVoOVurr4cgNlI5cSTIu7JjovhCc1WO6Hqb8jTVmY54qSfXrEIR1T1Q=="
    os.environ["EPIC_FHIR_BASE_URL"] = "https://fhir.epic.com/interconnect-fhir-oauth"
    os.environ["EPIC_REDIRECT_URI"] = "http://localhost:8000/callback"

if __name__ == "__main__":
    set_epic_env_vars()
    try:
        import importlib
        # Reload dotenv and epic_fhir_client to pick up env vars
        import dotenv
        importlib.reload(dotenv)
        import epic_fhir_client
        importlib.reload(epic_fhir_client)
        logger.info("Testing Epic FHIR client connectivity using integration/epic_fhir_client.py ...")
        try:
            # Try to get an access token using the client logic
            token = epic_fhir_client.get_access_token()
            logger.info(f"Successfully obtained access token: {token[:10]}... (truncated)")
            print("SUCCESS: Able to connect to Epic and obtain access token using epic_fhir_client.py.")
        except Exception as e:
            logger.error(f"Failed to obtain access token: {e}")
            print(f"FAILURE: Could not obtain access token from Epic using epic_fhir_client.py. Error: {e}")
    except Exception as e:
        logger.error(f"Error importing or running epic_fhir_client: {e}")
        print(f"ERROR: Could not import or run epic_fhir_client: {e}") 