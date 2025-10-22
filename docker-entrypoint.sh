#!/bin/bash
set -e

# Enable more detailed logging
if [ "$DEBUG" = "True" ]; then
  set -x  # Show all commands being executed
fi

echo >&2 "Starting BFlows OpenAPI Proxy initialization..."
echo >&2 "Checking network connectivity..."

# Test Internet connectivity
if ping -c 1 -W 5 8.8.8.8 >/dev/null 2>&1; then
  echo >&2 "Network connectivity: OK"
else
  echo >&2 "WARNING: Internet connectivity test failed. External API calls may not work."
fi

# Test DNS resolution
if nslookup google.com >/dev/null 2>&1; then
  echo >&2 "DNS resolution: OK"
else
  echo >&2 "WARNING: DNS resolution test failed. Adding fallback DNS servers."
  echo "nameserver 8.8.8.8" > /etc/resolv.conf
  echo "nameserver 8.8.4.4" >> /etc/resolv.conf
fi

# Test OpenAPI URL connection if provided
if [ -n "$OPENAPI_BASE_URL_RISK" ]; then
  BASE_URL=$(echo "$OPENAPI_BASE_URL_RISK" | sed 's|^\(https\?://\)\([^/]*\).*|\1\2|')
  echo >&2 "Testing connection to OpenAPI base URL: $BASE_URL"
  
  if curl -m 10 -s -o /dev/null -w "%{http_code}" "$BASE_URL" >/dev/null 2>&1; then
    echo >&2 "OpenAPI base URL connection: OK"
  else
    echo >&2 "WARNING: Could not connect to OpenAPI base URL. Verify URL and network settings."
  fi
fi

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

echo >&2 "Database initialization complete. Starting application..."

# Set additional Python environment variables for better error reporting
export PYTHONUNBUFFERED=1

# Run the application
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
