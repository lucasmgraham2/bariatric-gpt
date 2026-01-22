"""
Test the multi-agent AI system
Run this after all services are started
"""
import requests
import json

API_BASE = "http://localhost:8000"

def test_chat():
    """Test the multi-agent chat system"""
    
    print("Testing Multi-Agent AI System\n")
    print("=" * 60)
    
    # First, register and login to get a token
    print("\n1) Creating test user...")
    register_data = {
        "email": "testdoctor@example.com",
        "username": "testdoctor",
        "password": "test123"
    }
    
    try:
        response = requests.post(f"{API_BASE}/auth/register", json=register_data)
        if response.status_code == 200:
            result = response.json()
            token = result['access_token']
            print(f"User created. Token: {token[:20]}...")
        else:
            # User might already exist, try login
            print("User exists, logging in...")
            login_data = {
                "username": "testdoctor",
                "password": "test123"
            }
            response = requests.post(f"{API_BASE}/auth/login", json=login_data)
            result = response.json()
            token = result['access_token']
            print(f"Logged in. Token: {token[:20]}...")
    except Exception as e:
        print(f"Error: {e}")
        return
    
    # Test medical question (no patient data)
    print("\n" + "=" * 60)
    print("2) Testing Medical Question (No Patient Data)")
    print("=" * 60)
    print("Query: 'What are the main types of bariatric surgery?'\n")
    
    chat_data = {
        "message": "What are the main types of bariatric surgery?",
        "patient_id": None
    }
    
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        print("Waiting for AI response (first request may take 60-90 seconds)...")
        response = requests.post(
            f"{API_BASE}/chat",
            json=chat_data,
            headers=headers,
            timeout=120
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"\nAI Response:\n{result['response']}\n")
        else:
            print(f"Error: {response.status_code} - {response.text}")
    except requests.exceptions.Timeout:
        print("Request timed out. LLM service might be slow or not running.")
    except Exception as e:
        print(f"Error: {e}")
    
    # Test patient data query
    print("\n" + "=" * 60)
    print("3) Testing Patient Data Query")
    print("=" * 60)
    print("Query: 'What is patient 1's current weight?'\n")
    
    chat_data = {
        "message": "What is this patient's current weight?",
        "patient_id": "1"
    }
    
    try:
        print("Waiting for AI response (may take 30-60 seconds)...")
        response = requests.post(
            f"{API_BASE}/chat",
            json=chat_data,
            headers=headers,
            timeout=120
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"\nAI Response:\n{result['response']}\n")
        else:
            print(f"Error: {response.status_code} - {response.text}")
    except requests.exceptions.Timeout:
        print("Request timed out. LLM service might be slow or not running.")
    except Exception as e:
        print(f"Error: {e}")
    
    print("\n" + "=" * 60)
    print("Testing Complete!")
    print("=" * 60)
    print("\nIf you saw AI responses above, the system is working!")
    print("\nNext steps:")
    print("1. Open the Flutter app and navigate to AI Assistant")
    print("2. Try asking medical questions about diet, recovery, and surgery")
    print("3. Patient data features are ready to enable - see PROFILE_INTEGRATION_GUIDE.md")
    print("\nNote: Patient tools are currently disabled for simplicity.")

if __name__ == "__main__":
    print("Multi-Agent AI System Tester")
    print("Make sure all services are running:")
    print("  - Storage Service (port 8002)")
    print("  - API Gateway (port 8000)")
    print("  - LLM Service (port 8001)")
    print("  - Ollama with deepseek-r1:8b model")
    print()
    
    input("Press Enter to start test...")
    test_chat()
