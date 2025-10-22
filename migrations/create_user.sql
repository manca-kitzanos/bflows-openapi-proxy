-- Create user
CREATE USER openapi_user WITH PASSWORD 'openapi_password';

-- Grant privileges
GRANT USAGE ON SCHEMA openapi_schema TO openapi_user;
GRANT CREATE ON SCHEMA openapi_schema TO openapi_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA openapi_schema TO openapi_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA openapi_schema TO openapi_user;
GRANT ALL PRIVILEGES ON DATABASE "DBopenAPI" TO openapi_user;

-- Set default search path for database
ALTER DATABASE "DBopenAPI" SET search_path TO openapi_schema, public;
