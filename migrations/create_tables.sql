-- Set schema
SET search_path TO openapi_schema;

-- Create credit_score_responses table
CREATE TABLE IF NOT EXISTS credit_score_responses (
    id SERIAL PRIMARY KEY,
    identifier VARCHAR(255) NOT NULL,
    response_json JSONB,
    status_code INTEGER,
    status VARCHAR(20) DEFAULT 'ACTIVE' NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);

-- Add indexes for credit_score_responses
CREATE INDEX IF NOT EXISTS idx_credit_score_responses_identifier ON credit_score_responses(identifier);
CREATE INDEX IF NOT EXISTS idx_credit_score_responses_status ON credit_score_responses(status);

-- Create negativa_requests table
CREATE TABLE IF NOT EXISTS negativa_requests (
    id SERIAL PRIMARY KEY,
    external_id VARCHAR(255) NOT NULL,
    cf_piva VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING',
    version_status VARCHAR(20) DEFAULT 'ACTIVE' NOT NULL,
    request_json JSONB,
    response_json JSONB,
    callback_json JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);

-- Add index for version_status
CREATE INDEX IF NOT EXISTS idx_negativa_requests_version_status ON negativa_requests(version_status);

-- Add indexes for negativa_requests
CREATE INDEX IF NOT EXISTS idx_negativa_requests_external_id ON negativa_requests(external_id);
CREATE INDEX IF NOT EXISTS idx_negativa_requests_cf_piva ON negativa_requests(cf_piva);
CREATE INDEX IF NOT EXISTS idx_negativa_requests_status ON negativa_requests(status);

-- Create negativa_details table
CREATE TABLE IF NOT EXISTS negativa_details (
    id SERIAL PRIMARY KEY,
    request_id INTEGER NOT NULL REFERENCES negativa_requests(id),
    detail_json JSONB,
    presence_pregiudizievoli BOOLEAN DEFAULT FALSE,
    presence_procedure BOOLEAN DEFAULT FALSE,
    presence_protesti BOOLEAN DEFAULT FALSE,
    status_code INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);

-- Add indexes for negativa_details
CREATE INDEX IF NOT EXISTS idx_negativa_details_request_id ON negativa_details(request_id);

-- Grant permissions
ALTER TABLE credit_score_responses OWNER TO openapi_user;
ALTER TABLE negativa_requests OWNER TO openapi_user;
ALTER TABLE negativa_details OWNER TO openapi_user;
