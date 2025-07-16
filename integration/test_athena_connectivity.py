import requests
import json
from datetime import datetime, timedelta

BASE_URL = "https://clini-v7ur.onrender.com/api/tools"

# Real test data for comprehensive testing
TEST_PATIENT = {
    "name": "Gboyega ofi",
    "phone": "555-123-4567",
    "email": "Gboyegaofi@gmail.com",
    "dob": "24th octoberr , 2000",
    "address": "123 Main St",
    "city": "Anytown",
    "state": "CA",
    "zip": "90210"
}

# All endpoints from webhook_tools.py with real payloads
ENDPOINTS = [
    # Core appointment endpoints
    {
        "path": "/check-availability",
        "payload": {
            "department_id": "1",
            "date": "tomorrow",
            "service_type": "General Check-up",
            "patient_name": TEST_PATIENT["name"],
            "patient_phone": TEST_PATIENT["phone"]
        },
        "description": "Check appointment availability"
    },
    {
        "path": "/book-appointment",
        "payload": {
            "patient_name": TEST_PATIENT["name"],
            "patient_phone": TEST_PATIENT["phone"],
            "date": "06/30/2025",
            "time": "10:00 AM",
            "service_type": "General Check-up"
        },
        "description": "Book an appointment"
    },
    {
        "path": "/pre-check-patient",
        "payload": {
            "patient_name": TEST_PATIENT["name"],
            "patient_phone": TEST_PATIENT["phone"],
            "date_of_birth": TEST_PATIENT["dob"]
        },
        "description": "Pre-check if patient exists"
    },
    {
        "path": "/register-patient",
        "payload": {
            "patient_name": TEST_PATIENT["name"],
            "patient_phone": TEST_PATIENT["phone"],
            "date_of_birth": TEST_PATIENT["dob"],
            "email": TEST_PATIENT["email"],
            "address": TEST_PATIENT["address"],
            "city": TEST_PATIENT["city"],
            "state": TEST_PATIENT["state"],
            "zip_code": TEST_PATIENT["zip"]
        },
        "description": "Register new patient"
    },
    {
        "path": "/verify-patient",
        "payload": {
            "patient_name": TEST_PATIENT["name"],
            "patient_phone": TEST_PATIENT["phone"],
            "date_of_birth": TEST_PATIENT["dob"]
        },
        "description": "Verify patient information"
    },
    
    # Appointment management endpoints
    {
        "path": "/modify-appointment",
        "payload": {
            "action": "cancel",
            "patient_name": TEST_PATIENT["name"],
            "appointment_id": "12345"
        },
        "description": "Modify appointment (cancel)"
    },
    {
        "path": "/modify-appointment",
        "payload": {
            "action": "reschedule",
            "patient_name": TEST_PATIENT["name"],
            "appointment_id": "12345",
            "new_date": "07/01/2025",
            "new_time": "11:00 AM"
        },
        "description": "Modify appointment (reschedule)"
    },
    {
        "path": "/cancel-appointment",
        "payload": {
            "action": "cancel",
            "patient_name": TEST_PATIENT["name"],
            "appointment_id": "12345"
        },
        "description": "Cancel appointment"
    },
    {
        "path": "/reschedule-appointment",
        "payload": {
            "action": "reschedule",
            "patient_name": TEST_PATIENT["name"],
            "appointment_id": "12345",
            "new_date": "07/01/2025",
            "new_time": "11:00 AM"
        },
        "description": "Reschedule appointment"
    },
    
    # Insurance and practice info endpoints
    {
        "path": "/verify-insurance",
        "payload": {
            "patient_name": TEST_PATIENT["name"],
            "patient_phone": TEST_PATIENT["phone"],
            "insurance_provider": "Blue Cross Blue Shield"
        },
        "description": "Verify insurance"
    },
    {
        "path": "/check-insurance",
        "payload": {
            "patient_name": TEST_PATIENT["name"],
            "patient_phone": TEST_PATIENT["phone"],
            "insurance_provider": "Blue Cross Blue Shield"
        },
        "description": "Check insurance (alias)"
    },
    {
        "path": "/get-practice-info",
        "payload": {
            "info_type": "hours"
        },
        "description": "Get practice hours"
    },
    {
        "path": "/get-practice-info",
        "payload": {
            "info_type": "location"
        },
        "description": "Get practice location"
    },
    {
        "path": "/get-practice-info",
        "payload": {
            "info_type": "services",
            "specific_service": "General Check-up"
        },
        "description": "Get practice services"
    },
    {
        "path": "/get-directions",
        "payload": {
            "info_type": "location"
        },
        "description": "Get directions"
    },
    
    # Emergency and urgent care endpoints
    {
        "path": "/handle-emergency",
        "payload": {
            "urgency_level": "high",
            "symptoms": "chest pain and shortness of breath",
            "patient_name": TEST_PATIENT["name"],
            "patient_phone": TEST_PATIENT["phone"]
        },
        "description": "Handle emergency call"
    },
    {
        "path": "/handle-emergency",
        "payload": {
            "urgency_level": "low",
            "symptoms": "mild headache",
            "patient_name": TEST_PATIENT["name"],
            "patient_phone": TEST_PATIENT["phone"]
        },
        "description": "Handle non-emergency call"
    },
    
    # Office status and hours endpoints
    {
        "path": "/check-office-status",
        "payload": {
            "check_time": datetime.now().strftime("%Y-%m-%d %H:%M")
        },
        "description": "Check if office is open"
    },
    {
        "path": "/get-office-hours",
        "payload": {
            "day": "monday"
        },
        "description": "Get office hours for specific day"
    },
    {
        "path": "/check-holiday-hours",
        "payload": {
            "date": "2025-07-04"
        },
        "description": "Check holiday hours"
    },
    
    # Conversation management endpoints
    {
        "path": "/clarify-intent",
        "payload": {
            "unclear_input": "I want to see a doctor",
            "conversation_context": "appointment",
            "previous_attempts": 0,
            "patient_name": TEST_PATIENT["name"]
        },
        "description": "Clarify unclear intent"
    },
    {
        "path": "/conversation-recovery",
        "payload": {
            "error_type": "unclear_intent",
            "last_user_input": "help",
            "conversation_stage": "greeting",
            "retry_count": 0
        },
        "description": "Recover from conversation error"
    },
    {
        "path": "/suggest-alternatives",
        "payload": {
            "failed_action": "book_appointment",
            "patient_name": TEST_PATIENT["name"]
        },
        "description": "Suggest alternatives for failed action"
    },
    {
        "path": "/reset-conversation",
        "payload": {
            "patient_name": TEST_PATIENT["name"],
            "reason": "user_requested"
        },
        "description": "Reset conversation context"
    },
    
    # Name processing endpoint
    {
        "path": "/process-spelled-name",
        "payload": {
            "spelled_name": "J-O-H-N S-M-I-T-H",
            "context": "search",
            "original_name": "John Smith"
        },
        "description": "Process spelled name"
    }
]

def test_endpoint(endpoint_info):
    """Test a single endpoint with real payload"""
    url = BASE_URL + endpoint_info["path"]
    payload = endpoint_info["payload"]
    description = endpoint_info["description"]
    
    print(f"\n{'='*80}")
    print(f"Testing: {description}")
    print(f"Endpoint: {endpoint_info['path']}")
    print(f"URL: {url}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    print(f"{'='*80}")
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            try:
                response_data = response.json()
                print("✅ SUCCESS")
                print(f"Response: {json.dumps(response_data, indent=2)}")
                
                # Check for success indicator
                if response_data.get("success") is not None:
                    if response_data.get("success"):
                        print("✅ Endpoint returned success=True")
                    else:
                        print("⚠️  Endpoint returned success=False")
                        
            except json.JSONDecodeError:
                print("⚠️  Response is not valid JSON")
                print(f"Response text: {response.text}")
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            print(f"Response: {response.text}")
            
    except requests.exceptions.Timeout:
        print("❌ Request timed out")
    except requests.exceptions.ConnectionError:
        print("❌ Connection error - server may be down")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

def test_get_endpoint():
    """Test the GET /test endpoint"""
    url = BASE_URL + "/test"
    print(f"\n{'='*80}")
    print("Testing GET /test endpoint")
    print(f"URL: {url}")
    print(f"{'='*80}")
    
    try:
        response = requests.get(url, timeout=30)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            try:
                response_data = response.json()
                print("✅ SUCCESS")
                print(f"Response: {json.dumps(response_data, indent=2)}")
                
                # Check what endpoints are reported as available
                if "endpoints" in response_data:
                    print(f"📋 Available endpoints: {len(response_data['endpoints'])}")
                    for endpoint in response_data["endpoints"]:
                        print(f"   - {endpoint}")
                        
            except json.JSONDecodeError:
                print("⚠️  Response is not valid JSON")
                print(f"Response text: {response.text}")
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            print(f"Response: {response.text}")
            
    except requests.exceptions.Timeout:
        print("❌ Request timed out")
    except requests.exceptions.ConnectionError:
        print("❌ Connection error - server may be down")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

def main():
    """Run all endpoint tests"""
    print("🚀 Starting comprehensive webhook endpoint tests")
    print(f"Base URL: {BASE_URL}")
    print(f"Total endpoints to test: {len(ENDPOINTS)}")
    print(f"Test patient: {TEST_PATIENT['name']}")
    
    # Test all POST endpoints
    for endpoint_info in ENDPOINTS:
        test_endpoint(endpoint_info)
    
    # Test GET endpoint
    test_get_endpoint()
    
    print(f"\n{'='*80}")
    print("🎉 All webhook endpoint tests completed!")
    print(f"{'='*80}")

if __name__ == "__main__":
    main() 