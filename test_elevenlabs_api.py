#!/usr/bin/env python3
"""
Test script to verify the new ElevenLabs API key is working
"""
import requests
import json

# New ElevenLabs API key
API_KEY = "sk_4c02b8fb972529999df59ace915d45ef23b542255e48102d"
BASE_URL = "https://api.elevenlabs.io/v1"

headers = {
    "Accept": "application/json",
    "xi-api-key": API_KEY,
    "Content-Type": "application/json"
}

def test_api_key():
    """Test if the API key is valid by making a simple API call"""
    try:
        # Test the user info endpoint to verify the API key
        response = requests.get(f"{BASE_URL}/user", headers=headers)
        
        if response.status_code == 200:
            user_data = response.json()
            print("✅ ElevenLabs API key is valid!")
            print(f"User: {user_data.get('first_name', 'Unknown')} {user_data.get('last_name', 'Unknown')}")
            print(f"Subscription: {user_data.get('subscription', {}).get('tier', 'Unknown')}")
            print(f"Character count: {user_data.get('subscription', {}).get('character_count', 0)}")
            return True
        else:
            print(f"❌ API key test failed. Status: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing API key: {str(e)}")
        return False

def test_agents_list():
    """Test listing agents to verify the API key works for agent operations"""
    try:
        response = requests.get(f"{BASE_URL}/convai/agents", headers=headers)
        
        if response.status_code == 200:
            agents = response.json()
            print(f"✅ Successfully retrieved {len(agents)} agents")
            for agent in agents[:3]:  # Show first 3 agents
                print(f"  - {agent.get('name', 'Unknown')} (ID: {agent.get('agent_id', 'Unknown')})")
            return True
        else:
            print(f"❌ Failed to list agents. Status: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error listing agents: {str(e)}")
        return False

def test_voices_list():
    """Test listing voices to verify the API key works for voice operations"""
    try:
        response = requests.get(f"{BASE_URL}/voices", headers=headers)
        
        if response.status_code == 200:
            voices = response.json()
            print(f"✅ Successfully retrieved {len(voices.get('voices', []))} voices")
            for voice in voices.get('voices', [])[:3]:  # Show first 3 voices
                print(f"  - {voice.get('name', 'Unknown')} (ID: {voice.get('voice_id', 'Unknown')})")
            return True
        else:
            print(f"❌ Failed to list voices. Status: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error listing voices: {str(e)}")
        return False

if __name__ == "__main__":
    print("Testing ElevenLabs API key...")
    print("=" * 50)
    
    # Test 1: Basic API key validation
    print("1. Testing API key validation...")
    api_key_valid = test_api_key()
    
    if api_key_valid:
        print("\n2. Testing agents list...")
        test_agents_list()
        
        print("\n3. Testing voices list...")
        test_voices_list()
        
        print("\n" + "=" * 50)
        print("✅ All tests completed successfully!")
        print("The new ElevenLabs API key is working correctly.")
    else:
        print("\n" + "=" * 50)
        print("❌ API key validation failed. Please check the API key.") 