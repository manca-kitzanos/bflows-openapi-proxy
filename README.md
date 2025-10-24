# Bflows OpenAPI Proxy

A FastAPI proxy service for OpenAPI with database caching, versioning support, and email notifications.

## Features

- Proxies requests to OpenAPI service with Bearer token authentication
- Stores responses in a PostgreSQL database for caching and versioning
- Supports versioning of responses with ACTIVE/NOT ACTIVE status
- Supports both fresh data fetching and cached data retrieval
- Email notifications when asynchronous data becomes available via webhooks
- Proper error handling for OpenAPI responses
- Unified combined endpoint for fetching data from all available sources
- Timezone support for all timestamps
- Support for both TLS and SSL email connections

## Docker Setup

The project is fully dockerized, making it easy to set up and run without any local dependencies other than Docker and Docker Compose.

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/)
- The "public" Docker network (must be created before running the application)

### Network Configuration

The application requires an external Docker network called "public" for deployment with fixed IPs. Create it if it doesn't exist:

```bash
docker network create --subnet=172.25.0.0/16 public
```

This allows the application to be accessible via a reverse proxy at `https://openapi-proxy.bflows.ai`.

### Environment Configuration

#### General Configuration

All configuration is done through the `.env` file. The repository includes two example files:

1. **`.env.local.example`** - For local development with database on localhost
2. **`.env.docker.example`** - For Docker deployment with fixed IPs

Choose the appropriate one based on your deployment:

```bash
# For local development:
cp .env.local.example .env
nano .env  # or use any text editor

# OR for Docker deployment:
cp .env.docker.example .env
nano .env  # or use any text editor
```

The example files contain all required variables with appropriate defaults for each environment:

**Local Environment Example:**
```env
# Database configuration
DB_HOST=localhost
DB_PORT=5432
DB_NAME=DBopenAPI
# ... other variables
```

**Docker Environment Example:**
```env
# Database configuration
DB_HOST=172.25.0.101  # Fixed IP for PostgreSQL container
DB_PORT=5432
DB_NAME=DBopenAPI
# ... other variables
```

Modify the values as needed for your environment. Note that `DB_HOST` is automatically set to the fixed IP of the PostgreSQL container (172.25.0.101) in the Docker Compose configuration.

#### Email Configuration

The application supports email notifications for asynchronous data requests. Configure the following parameters in your `.env` file:

```env
# Email settings
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_USE_SSL=False
EMAIL_HOST_USER=your_email@gmail.com
EMAIL_HOST_PASSWORD=your_app_password
DEFAULT_FROM_EMAIL=your_email@gmail.com
DEFAULT_NOTIFICATION_EMAIL=default@example.com
```

- `EMAIL_HOST`: SMTP server address (e.g., smtp.gmail.com)
- `EMAIL_PORT`: SMTP server port (587 for TLS, 465 for SSL)
- `EMAIL_USE_TLS`: Set to "True" to use TLS for secure connection
- `EMAIL_USE_SSL`: Set to "True" to use SSL for secure connection (alternative to TLS)
- `EMAIL_HOST_USER`: Your email address
- `EMAIL_HOST_PASSWORD`: Your email password or app-specific password
- `DEFAULT_FROM_EMAIL`: Email address to use in the From field
- `DEFAULT_NOTIFICATION_EMAIL`: Default email to send notifications to when not specified in the API call

**Note**: For Gmail, you'll need to create an "App Password" if you have 2FA enabled. Standard password authentication won't work.

### Database Migrations

When running with Docker, all migrations are automatically applied during container startup via the `docker-entrypoint.sh` script. If you need to run migrations manually:

```bash
# Inside Docker container
python migrations/run_migrations.py

# Or to run a specific migration
psql -U postgres -d DBopenAPI -f migrations/create_tables.sql
psql -U postgres -d DBopenAPI -f migrations/add_email_callback_columns.sql
```

### Running with Docker Compose

1. Ensure the "public" network exists (see Network Configuration above)

2. Build and start the containers:

```bash
docker-compose up -d
```

3. The application will be available at:
   - Local development: http://localhost:8000
   - Production deployment: https://openapi-proxy.bflows.ai

4. Access the Swagger UI documentation at /docs (append to either URL above)

### Network Details

The containers use the following fixed IPs in the "public" network:
- PostgreSQL: 172.25.0.101
- API Application: 172.25.0.102

### Accessing the Database

The PostgreSQL database is exposed on port 5435 (mapped to internal port 5432). You can connect to it using:

```bash
psql -h localhost -p 5435 -U postgres -d DBopenAPI
```

Use the password specified in your `.env` file for `DB_ROOT_PASSWORD`.

## API Usage

### Endpoints

#### Credit Score Endpoints

- `GET /credit-score/{identifier}?update=false` - Get cached data for an identifier
- `GET /credit-score/{identifier}?update=true` - Force refresh data for an identifier
- Parameters:
  - `identifier`: VAT code, tax code, or company ID (required)
  - `update`: When true, forces a fresh fetch from OpenAPI (optional, default: false)

#### Negative Events Endpoints

- `GET /negative-event?cf_piva=TAXCODE123456` - Unified endpoint for negative event checks
  - Use with `update=false` (default) to get cached data or create new request if none exists
  - Use with `update=true` to force a new request and mark previous records as inactive
  - Example: `GET /negative-event?cf_piva=ABC123&update=true&email_callback=user@example.com`
- Parameters:
  - `cf_piva`: Tax code or VAT number to check (required)
  - `update`: When true, forces a new request (optional, default: false)
  - `email_callback`: Email address to notify when data is ready (optional)
  
- `POST /webhook/negative-event` - Hidden webhook endpoint (not exposed in Swagger UI) for receiving callbacks from OpenAPI

#### Company Full Data Endpoints

- `GET /company-full/{identifier}` - Get comprehensive company data with 400+ financial details
  - Use with `update=false` (default) to get cached data if available, or start a new request
  - Use with `update=true` to force a new request and mark previous records as inactive
  - Example: `GET /company-full/12345678901?update=true&email_callback=user@example.com`
- Parameters:
  - `identifier`: VAT code or tax code of the company (required)
  - `update`: When true, forces a new request (optional, default: false)
  - `email_callback`: Email address to notify when data is ready (optional)
  
- `POST /webhook/company-full` - Hidden webhook endpoint (not exposed in Swagger UI) for receiving company data callbacks from OpenAPI

#### Combined Data Endpoint

- `GET /company-all-data` - Fetch comprehensive data from all available endpoints in a single call
  - Calls credit-score, company-full, and negative-event endpoints and combines results
  - Example: `GET /company-all-data?identifier=12345678901&update=true&email_callback=user@example.com`
- Parameters:
  - `identifier`: VAT code, tax code, or company ID (required)
  - `update`: When true, forces a fresh fetch for all endpoints (optional, default: false)
  - `email_callback`: Email address to notify when asynchronous data is ready (optional)
- Response format:
  ```json
  {
    "credit_score": { /* data from credit-score endpoint */ },
    "company_data": { /* data from company-full endpoint */ },
    "negative_events": { /* data from negative-event endpoint */ }
  }
  ```

### Email Notification Feature

For asynchronous endpoints (company-full and negative-event), you can receive an email notification when data becomes available:

1. Add the `email_callback` parameter to your request with your email address:
   ```
   GET /company-full/12345678901?email_callback=your_email@example.com
   ```

2. If no email is provided, the system will use the `DEFAULT_NOTIFICATION_EMAIL` from settings.

3. When the webhook callback is received from OpenAPI, the system will:
   - Update the record in the database
   - Send an email notification to the stored email address
   - Include relevant data (like company name, tax code, etc.) in the email

### Response Format

Example response format for individual endpoints:

```json
{
  "id": 1,
  "identifier": "12345678901",
  "response_json": { ... },
  "status_code": 200,
  "status": "ACTIVE",
  "created_at": "2025-10-22T07:57:54.876653+00:00",
  "updated_at": null
}
```

## Development Setup

For local development without Docker:

1. Install PostgreSQL 16
2. Create the database, schema, and user as defined in your `.env` file
3. Run the initial migrations:
   ```bash
   psql -U postgres -d DBopenAPI -f migrations/create_tables.sql
   psql -U postgres -d DBopenAPI -f migrations/add_email_callback_columns.sql
   ```
4. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
5. Run the application:
   ```bash
   uvicorn app.main:app --reload
   ```

## Troubleshooting

### Email Notifications Not Working

1. Check your SMTP settings in the `.env` file
2. For Gmail, ensure you're using an App Password if you have 2FA enabled
3. Verify the correct port is being used (587 for TLS, 465 for SSL)
4. Check the application logs for SMTP connection errors

### Database Connection Issues

1. Verify PostgreSQL is running and accepting connections
2. Check the database credentials in `.env` match your PostgreSQL setup
3. Ensure the database and schema exist as specified in your configuration

### Missing email_callback Columns

If you're seeing errors about missing columns:

1. Run the email_callback column migration:
   ```bash
   psql -U postgres -d DBopenAPI -f migrations/add_email_callback_columns.sql
   ```
2. Restart the application to apply the changes
