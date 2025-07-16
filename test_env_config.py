import os

# Print the current database URL
print(f"DATABASE_URL: {os.getenv('DATABASE_URL')}")

# Print the ElevenLabs API key (with partial masking for safety)
elevenlabs_api_key = os.getenv('ELEVENLABS_API_KEY')
if elevenlabs_api_key:
    print(f"ELEVENLABS_API_KEY: {elevenlabs_api_key[:8]}...{elevenlabs_api_key[-4:]}")
else:
    # Check fallback in agent_setup_service.py or setup_service.py
    fallback = 'sk_911c468b5acba9938859200fdc4f9b8ffa8584b7b17e7487'
    print(f"ELEVENLABS_API_KEY: (env not set, fallback in use) {fallback[:8]}...{fallback[-4:]}") 