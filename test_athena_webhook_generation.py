#!/usr/bin/env python3
"""
Test script to generate Athena Health webhook tools
"""
import requests
import json

def test_athena_webhook_generation():
    """Test the webhook tools generation endpoint for Athena Health"""
    
    # API endpoint
    url = "https://clini-v7ur.onrender.com/api/agent-setup/generate-webhook-tools"
    
    # Request payload with Athena Health credentials
    payload = {
        "clinic_id": "test_clinic_001",
        "ehr": "athena",
        "athena_creds": {
            "athena_client_id": "0oay0ra7o9QjMriHJ297",
            "athena_client_secret": "-c8EYvTZtB-kUdEZCq1I_1ZYqFuuTwal626YM0W8C-QHKA-6nX2ngmPaJMrBfgfw",
            "athena_api_base_url": "https://api.preview.platform.athenahealth.com",
            "athena_practice_id": "195900"
        },
        "epic_creds": None
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        print("Generating Athena Health webhook tools...")
        print("=" * 60)
        
        response = requests.post(url, json=payload, headers=headers)
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Successfully generated webhook tools!")
            print(f"Response status: {response.status_code}")
            
            # Extract and display the tools
            conversation_config = result.get("conversation_config", {})
            agent_config = conversation_config.get("agent", {})
            prompt_config = agent_config.get("prompt", {})
            tools = prompt_config.get("tools", [])
            
            print(f"\n📋 Generated {len(tools)} webhook tools:")
            print("-" * 40)
            
            for i, tool in enumerate(tools, 1):
                print(f"{i}. {tool.get('name', 'Unknown')}")
                print(f"   Description: {tool.get('description', 'No description')}")
                print(f"   URL: {tool.get('api_schema', {}).get('url', 'No URL')}")
                print()
            
            # Save the response to a file
            with open("generated_athena_webhook_tools.json", "w") as f:
                json.dump(result, f, indent=2)
            print("💾 Response saved to 'generated_athena_webhook_tools.json'")
            
            return True
            
        else:
            print(f"❌ Failed to generate webhook tools. Status: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error generating webhook tools: {str(e)}")
        return False

def test_auto_update_tools():
    """Test the auto-update tools endpoint for Athena Health"""
    
    # API endpoint
    url = "https://a962b0243a61.ngrok-free.app/api/agent-setup/auto-update-tools"
    
    # Request payload with Athena Health credentials
    payload = {
        "clinic_id": "test_clinic_001",
        "ehr": "athena",
        "athena_creds": {
            "athena_client_id": "0oay0ra7o9QjMriHJ297",
            "athena_client_secret": "-c8EYvTZtB-kUdEZCq1I_1ZYqFuuTwal626YM0W8C-QHKA-6nX2ngmPaJMrBfgfw",
            "athena_api_base_url": "https://api.preview.platform.athenahealth.com",
            "athena_practice_id": "195900"
        },
        "epic_creds": None
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        print("\nTesting auto-update tools endpoint...")
        print("=" * 60)
        
        response = requests.post(url, json=payload, headers=headers)
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Successfully auto-updated tools!")
            print(f"Response status: {response.status_code}")
            
            # Display the result
            print(f"Success: {result.get('success', False)}")
            webhooks = result.get('webhooks', [])
            print(f"Generated {len(webhooks)} webhook tools")
            
            return True
            
        else:
            print(f"❌ Failed to auto-update tools. Status: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error auto-updating tools: {str(e)}")
        return False

if __name__ == "__main__":
    print("Testing Athena Health Webhook Tools Generation")
    print("=" * 60)
    
    # Test 1: Generate webhook tools
    success1 = test_athena_webhook_generation()
    
    # Test 2: Auto-update tools (if you have an existing agent)
    success2 = test_auto_update_tools()
    
    print("\n" + "=" * 60)
    if success1 and success2:
        print("✅ All tests completed successfully!")
    elif success1:
        print("✅ Webhook tools generation successful!")
        print("⚠️  Auto-update tools failed (may need existing agent)")
    else:
        print("❌ Tests failed. Please check the server and credentials.") 