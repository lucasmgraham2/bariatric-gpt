#!/bin/bash
# macOS PostgreSQL Setup for Bariatric GPT

echo "Setting up PostgreSQL database for Bariatric GPT on macOS..."
echo

# Check if Homebrew is installed
if ! command -v brew &> /dev/null; then
    echo "Homebrew not found. Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

# Install PostgreSQL if not already installed
if ! command -v psql &> /dev/null; then
    echo "Installing PostgreSQL..."
    brew install postgresql@15
    brew services start postgresql@15
    
    # Wait for PostgreSQL to start
    echo "Waiting for PostgreSQL to start..."
    sleep 5
else
    echo "PostgreSQL already installed"
    # Make sure it's running
    brew services start postgresql@15 2>/dev/null || true
fi

# Create user and database
echo "Creating database and user..."

# Use the default postgres user to create our custom user and database
psql postgres -c "DROP DATABASE IF EXISTS bariatric_db;" 2>/dev/null || true
psql postgres -c "DROP USER IF EXISTS bariatric_user;" 2>/dev/null || true

psql postgres -c "CREATE USER bariatric_user WITH PASSWORD 'bariatric_password';"
psql postgres -c "CREATE DATABASE bariatric_db OWNER bariatric_user;"
psql postgres -c "GRANT ALL PRIVILEGES ON DATABASE bariatric_db TO bariatric_user;"

echo
echo "PostgreSQL setup complete!"
echo "Database: bariatric_db"
echo "User: bariatric_user"
echo "Password: bariatric_password"
echo "Host: localhost"
echo "Port: 5432"
echo
echo "Next steps:"
echo "1. python storage_service/main_simple.py    # Terminal 1"
echo "2. python api_gateway/main_simple.py        # Terminal 2"
echo "3. cd flutter_frontend && flutter run       # Terminal 3"