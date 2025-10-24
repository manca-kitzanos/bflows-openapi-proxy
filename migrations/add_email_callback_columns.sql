-- Set schema
SET search_path TO openapi_schema;

-- Add email_callback column to company_full_data table
ALTER TABLE company_full_data 
ADD COLUMN IF NOT EXISTS email_callback VARCHAR(255);

-- Add email_callback column to negativa_requests table
ALTER TABLE negativa_requests 
ADD COLUMN IF NOT EXISTS email_callback VARCHAR(255);

-- Grant permissions
ALTER TABLE company_full_data OWNER TO openapi_user;
ALTER TABLE negativa_requests OWNER TO openapi_user;
