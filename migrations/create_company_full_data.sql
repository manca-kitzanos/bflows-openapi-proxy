-- Create company_full_data table
CREATE TABLE IF NOT EXISTS company_full_data (
    id SERIAL PRIMARY KEY,
    identifier VARCHAR NOT NULL,
    external_id VARCHAR,
    status VARCHAR NOT NULL DEFAULT 'PENDING',
    version_status VARCHAR NOT NULL DEFAULT 'ACTIVE',
    request_json JSONB,
    response_json JSONB,
    callback_json JSONB,
    status_code INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_company_full_data_identifier ON company_full_data(identifier);
CREATE INDEX IF NOT EXISTS idx_company_full_data_external_id ON company_full_data(external_id);
CREATE INDEX IF NOT EXISTS idx_company_full_data_status ON company_full_data(status);
CREATE INDEX IF NOT EXISTS idx_company_full_data_version_status ON company_full_data(version_status);
