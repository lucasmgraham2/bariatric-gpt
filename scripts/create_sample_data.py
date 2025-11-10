"""
Sample data creation script for Bariatric GPT
Run this after setting up the database to create test users
"""
import requests
import json

API_BASE = "http://localhost:8000"

def create_sample_users():
    """Create sample users for testing"""
    sample_users = [
        {
            "email": "john.doe@example.com",
            "username": "john_doe", 
            "password": "testpass123"
        },
        {
            "email": "jane.smith@example.com", 
            "username": "jane_smith",
            "password": "testpass123"
        },
        {
            "email": "mike.wilson@example.com",
            "username": "mike_wilson", 
            "password": "testpass123"
        }
    ]
    
    print("Creating sample users...")
    
    for user in sample_users:
        try:
            response = requests.post(
                f"{API_BASE}/auth/register",
                json=user,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Created user: {user['username']} (ID: {result.get('user_id')})")
            else:
                print(f"❌ Failed to create {user['username']}: {response.text}")
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Error creating {user['username']}: {e}")
    
    print("\nSample data creation complete!")
    print("You can now test login with any of these accounts:")
    for user in sample_users:
        print(f"  Username: {user['username']}, Password: {user['password']}")

if __name__ == "__main__":
    print("🗂️  Bariatric GPT Sample Data Creator")
    print("Make sure your services are running:")
    print("  - Storage Service: http://localhost:8002")  
    print("  - API Gateway: http://localhost:8000")
    print()
    
    response = input("Continue? (y/N): ")
    if response.lower() == 'y':
        create_sample_users()
    else:
        print("Cancelled.")