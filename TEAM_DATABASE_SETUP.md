# Team Database Setup Guide

## For New Team Members

### Windows Users:
1. **Clone the repository**
2. **Run the automated setup**:
   ```bash
   setup_windows_postgres.bat
   ```
3. **Start the services**:
   ```bash
   python storage_service/main_simple.py    # Terminal 1
   python api_gateway/main_simple.py        # Terminal 2  
   cd flutter_frontend && flutter run       # Terminal 3
   ```

### macOS Users:
1. **Clone the repository**
2. **Run the automated setup**:
   ```bash
   chmod +x setup_macos_postgres.sh
   ./setup_macos_postgres.sh
   ```
3. **Start the services** (same as Windows):
   ```bash
   python storage_service/main_simple.py    # Terminal 1
   python api_gateway/main_simple.py        # Terminal 2  
   cd flutter_frontend && flutter run       # Terminal 3
   ```

### Manual Setup (Any OS):
1. **Install PostgreSQL** from https://www.postgresql.org/download/
2. **Create database manually**:
   ```sql
   CREATE USER bariatric_user WITH PASSWORD 'bariatric_password';
   CREATE DATABASE bariatric_db OWNER bariatric_user;
   GRANT ALL PRIVILEGES ON DATABASE bariatric_db TO bariatric_user;
   ```

## What's Shared vs Local

### Shared in Git (Team assets):
- Database schema (auto-created by FastAPI)
- Setup scripts (`setup_windows_postgres.bat`, `setup_windows_postgres.sql`)
- Documentation (this file)
- Application code
- Migration scripts (future)

### NOT in Git (Local only):
- Actual database files (`.gitignore`d)
- User data and passwords
- Local configuration files
- Environment-specific settings

## Data Sharing Strategies

### For Development:
1. **Each developer has their own local database**
2. **Share sample data scripts** (if needed)
3. **Use migrations** for schema changes

### For Production:
- Use cloud databases (AWS RDS, Google Cloud SQL, etc.)
- Separate staging/production environments
- Proper backup and restore procedures

## Sample Data Script
```python
# scripts/create_sample_users.py
import requests

users = [
    {"email": "john@example.com", "username": "john_doe", "password": "password123"},
    {"email": "jane@example.com", "username": "jane_smith", "password": "password123"},
]

for user in users:
    response = requests.post("http://localhost:8000/auth/register", json=user)
    print(f"Created user: {user['username']} - {response.status_code}")
```

## Security Notes
- Change default passwords in production
- Use environment variables for sensitive config
- Never commit real user data
- Use different databases for dev/staging/production