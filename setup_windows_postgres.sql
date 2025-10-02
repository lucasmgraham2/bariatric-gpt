-- Setup script for Windows PostgreSQL
-- Run this after installing PostgreSQL on Windows

-- Create the bariatric_user
CREATE USER bariatric_user WITH PASSWORD 'bariatric_password';

-- Create the database
CREATE DATABASE bariatric_db OWNER bariatric_user;

-- Grant all privileges
GRANT ALL PRIVILEGES ON DATABASE bariatric_db TO bariatric_user;

-- Connect to the database and grant schema privileges
\c bariatric_db;
GRANT ALL PRIVILEGES ON SCHEMA public TO bariatric_user;
GRANT CREATE ON SCHEMA public TO bariatric_user;

-- Verify the setup
SELECT datname FROM pg_database WHERE datname = 'bariatric_db';
SELECT usename FROM pg_user WHERE usename = 'bariatric_user';

\echo 'Setup complete! Database and user created successfully.'