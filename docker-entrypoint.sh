#!/bin/bash
set -e

# Function to check if PostgreSQL is up and running
postgres_ready() {
  PGPASSWORD="$DB_ROOT_PASSWORD" psql -h "$DB_HOST" -U "$DB_ROOT_USER" -c "SELECT 1" > /dev/null 2>&1
}

# Wait for PostgreSQL to be ready
until postgres_ready; do
  echo >&2 "PostgreSQL is unavailable - sleeping"
  sleep 1
done

echo >&2 "PostgreSQL is up - executing command"

# Create database and schema if they don't exist
PGPASSWORD="$DB_ROOT_PASSWORD" psql -h "$DB_HOST" -U "$DB_ROOT_USER" -c "SELECT 1 FROM pg_database WHERE datname = '$DB_NAME'" | grep -q 1 || PGPASSWORD="$DB_ROOT_PASSWORD" psql -h "$DB_HOST" -U "$DB_ROOT_USER" -c "CREATE DATABASE \"$DB_NAME\";"

# Connect to the newly created database and create the schema and user
PGPASSWORD="$DB_ROOT_PASSWORD" psql -h "$DB_HOST" -U "$DB_ROOT_USER" -d "$DB_NAME" -c "CREATE SCHEMA IF NOT EXISTS $DB_SCHEMA;"
PGPASSWORD="$DB_ROOT_PASSWORD" psql -h "$DB_HOST" -U "$DB_ROOT_USER" -d "$DB_NAME" -c "DO \$\$ BEGIN CREATE ROLE $DB_USER WITH LOGIN PASSWORD '$DB_PASSWORD'; EXCEPTION WHEN duplicate_object THEN RAISE NOTICE 'User already exists'; END \$\$;"
PGPASSWORD="$DB_ROOT_PASSWORD" psql -h "$DB_HOST" -U "$DB_ROOT_USER" -d "$DB_NAME" -c "GRANT ALL PRIVILEGES ON SCHEMA $DB_SCHEMA TO $DB_USER;"
PGPASSWORD="$DB_ROOT_PASSWORD" psql -h "$DB_HOST" -U "$DB_ROOT_USER" -d "$DB_NAME" -c "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA $DB_SCHEMA TO $DB_USER;"
PGPASSWORD="$DB_ROOT_PASSWORD" psql -h "$DB_HOST" -U "$DB_ROOT_USER" -d "$DB_NAME" -c "GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA $DB_SCHEMA TO $DB_USER;"

# Run the application
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
