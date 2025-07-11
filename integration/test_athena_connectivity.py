import os
import logging
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def set_athena_env_vars():
    os.environ["ATHENA_CLIENT_ID"] = "0oay0ra7o9QjMriHJ297"
    os.environ["ATHENA_CLIENT_SECRET"] = "-c8EYvTZtB-kUdEZCq1I_1ZYqFuuTwal626YM0W8C-QHKA-6nX2ngmPaJMrBfgfw"
    os.environ["ATHENA_API_BASE_URL"] = "https://api.preview.platform.athenahealth.com"
    os.environ["ATHENA_PRACTICE_ID"] = "195900"

if __name__ == "__main__":
    set_athena_env_vars()
    try:
        import importlib
        import athena_health_client
        importlib.reload(athena_health_client)
        logger.info("Testing AthenaHealth API connectivity using integration/athena_health_client.py ...")
        try:
            token = athena_health_client.get_access_token()
            logger.info(f"Successfully obtained access token: {token[:10]}... (truncated)")
            print("SUCCESS: Able to connect to AthenaHealth and obtain access token.")
            # Try a simple API call (e.g., get practice info)
            result = athena_health_client.get_all_providers()
            if result.get("success"):
                logger.info(f"Successfully fetched providers: count={result.get('count')}")
                print("SUCCESS: Able to fetch providers from AthenaHealth API.")
            else:
                logger.error(f"Failed to fetch providers: {result}")
                print("FAILURE: Could not fetch providers from AthenaHealth API.")
        except Exception as e:
            logger.error(f"Failed to connect to AthenaHealth: {e}")
            print(f"FAILURE: Could not connect to AthenaHealth API. Error: {e}")
    except Exception as e:
        logger.error(f"Error importing or running athena_health_client: {e}")
        print(f"ERROR: Could not import or run athena_health_client: {e}") 