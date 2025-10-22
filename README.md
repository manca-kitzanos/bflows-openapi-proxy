# Bflows OpenAPI Proxy

A FastAPI proxy service for OpenAPI with database caching and versioning support.

## Features

- Proxies requests to OpenAPI service with Bearer token authentication
- Stores responses in a PostgreSQL database for caching and versioning
- Supports versioning of responses with ACTIVE/NOT ACTIVE status
- Supports both fresh data fetching and cached data retrieval
- Proper error handling for OpenAPI responses
- Timezone support for all timestamps

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

#### Negative Events Endpoints

- `POST /negative-event` - Create a new negative event check request
- `POST /webhook/negative-event` - Webhook for receiving callbacks from OpenAPI
- `GET /negative-event/{request_id}` - Get details for a specific request
- `GET /negative-event/by-tax/{cf_piva}` - Get latest completed request for a tax code/VAT number

### Response Format

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
3. Install Python dependencies:

```bash
pip install -r requirements.txt
```

4. Run the application:

```bash
uvicorn app.main:app --reload
```
