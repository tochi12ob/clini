#!/bin/bash

# Example curl command to generate Athena Health webhook tools
# Replace the URL with your actual server URL

curl -X POST "https://d20c8d64dbc3.ngrok-free.app/api/agent-setup/generate-webhook-tools" \
  -H "Content-Type: application/json" \
  -d '{
    "clinic_id": "test_clinic_001",
    "ehr": "athena",
    "athena_creds": {
      "athena_client_id": "0oay0ra7o9QjMriHJ297",
      "athena_client_secret": "-c8EYvTZtB-kUdEZCq1I_1ZYqFuuTwal626YM0W8C-QHKA-6nX2ngmPaJMrBfgfw",
      "athena_api_base_url": "https://api.preview.platform.athenahealth.com",
      "athena_practice_id": "195900"
    },
    "epic_creds": null
  }'

echo ""
echo "This will return a conversation_config JSON with Athena Health webhook tools configured." 