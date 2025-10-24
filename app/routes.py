from fastapi import APIRouter, Depends, HTTPException, Path, Query, BackgroundTasks, Request, Body
from sqlalchemy.orm import Session
from . import database, models, schemas, email_utils, settings
import httpx
import os
import json
from typing import Dict, Any, Optional
from fastapi.openapi.utils import get_openapi
from fastapi.routing import APIRoute

router = APIRouter(
    tags=["OpenAPI Proxy"]
)

# Custom OpenAPI function to hide webhook endpoints
def custom_openapi(app):
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        tags=app.openapi_tags,
    )
    
    # Filter out webhook endpoints from the schema
    paths = openapi_schema["paths"]
    filtered_paths = {}
    for path, path_item in paths.items():
        if not path.startswith("/webhook"):
            filtered_paths[path] = path_item
    
    openapi_schema["paths"] = filtered_paths
    app.openapi_schema = openapi_schema
    return app.openapi_schema

# Load environment variables
OPENAPI_BASE_URL_RISK = os.getenv("OPENAPI_BASE_URL_RISK")
OPENAPI_TOKEN_RISK = os.getenv("OPENAPI_TOKEN_RISK")
OPENAPI_BASE_URL_COMPANY = os.getenv("OPENAPI_BASE_URL_COMPANY")
OPENAPI_TOKEN_COMPANY = os.getenv("OPENAPI_TOKEN_COMPANY")

# Headers with Bearer token authentication
def get_auth_headers_risk():
    return {"Authorization": f"Bearer {OPENAPI_TOKEN_RISK}"}

def get_auth_headers_company():
    return {"Authorization": f"Bearer {OPENAPI_TOKEN_COMPANY}"}

@router.get("/credit-score/{identifier}")  # Completely remove response_model instead of setting to None
async def get_credit_score(
    identifier: str = Path(..., description="VAT code, tax code, or company ID of the organization to fetch credit score for"),
    update: bool = Query(
        False, 
        description="When true, forces a fetch from OpenAPI and creates a new record; when false (default), returns existing record or 404"
    ),
    db: Session = Depends(database.get_db)
):
    """
    Fetch or update credit score data from the OpenAPI source.
    
    ## Description
    This endpoint provides credit score information for organizations by their identifiers.
    
    ## Behavior
    - If `update=false` (default):
      - If an ACTIVE record exists: Returns the existing record from the database
      - If no ACTIVE record exists: Creates a new "ACTIVE" record (fetches from OpenAPI)
    
    - If `update=true`:
      - If an ACTIVE record exists: Marks it as "NOT ACTIVE" and creates a new "ACTIVE" record
      - If no ACTIVE record exists: Creates a new "ACTIVE" record
    
    ## Response
    - For existing records: Returns only the "data" field from response_json with all credit score details
    - For new/updated records: Returns the full record with all fields (id, identifier, response_json, etc.)
    
    ## Example Usage
    - Get cached data: `GET /credit-score/ABC123`
    - Force refresh: `GET /credit-score/ABC123?update=true`
    """
    # Check if we already have an ACTIVE record for this identifier
    existing_response = db.query(models.CreditScoreResponse).filter(
        models.CreditScoreResponse.identifier == identifier,
        models.CreditScoreResponse.status == "ACTIVE"
    ).first()
    
    # Case 1: update=false/not set and record exists - return only the "data" field
    if not update and existing_response:
        # If we have a response_json with a "data" field, return just that data
        if existing_response and existing_response.response_json and "data" in existing_response.response_json:
            return existing_response.response_json["data"]
        return existing_response
        
    # All other cases (update=true OR no existing record) will fetch a new record from OpenAPI
    
    # For update=true, proceed to call the OpenAPI endpoint
    url = f"{OPENAPI_BASE_URL_RISK}/IT-creditscore-top/{identifier}"
    status_code = 500
    response_json = {}
    
    try:
        # Check if we're in a testing/development environment
        if "esempio.com" in OPENAPI_BASE_URL_RISK:
            # Provide mock data for testing
            print(f"Using mock data for {identifier} since actual OpenAPI URL is not available")
            status_code = 200
            response_json = {
                "company_id": identifier,
                "credit_score": {
                    "overall_score": 85,
                    "operational_credit_limit": 500000,
                    "rating": "A",
                    "risk_level": "Low"
                },
                "financial_data": {
                    "annual_revenue": 2500000,
                    "profit_margin": 15.3,
                    "debt_to_equity": 0.45,
                    "current_ratio": 2.1
                },
                "history": {
                    "founded": "2005-08-15",
                    "previous_scores": [
                        {"date": "2023-01-15", "score": 82},
                        {"date": "2022-07-15", "score": 80},
                        {"date": "2022-01-15", "score": 78}
                    ]
                },
                "timestamp": "2023-07-15T14:30:00Z"
            }
        else:
            # Proceed with actual API call
            async with httpx.AsyncClient() as client:
                try:
                    # Prepare headers
                    headers = get_auth_headers_risk()
                    headers["accept"] = "application/json"
                    
                    # Log the URL and headers for debugging (omitting the auth token for security)
                    headers_log = headers.copy()
                    if "Authorization" in headers_log:
                        headers_log["Authorization"] = "Bearer [REDACTED]"
                    print(f"Making OpenAPI request to: {url}")
                    print(f"Headers: {headers_log}")
                    
                    # Make the request
                    resp = await client.get(
                        url,
                        headers=headers,
                        timeout=30.0  # Add a timeout to avoid hanging indefinitely
                    )
                    status_code = resp.status_code
                    
                    # Parse the JSON response regardless of status code
                    try:
                        response_json = resp.json()
                    except Exception as json_err:
                        # Handle case where response isn't valid JSON
                        response_json = {
                            "error": f"Invalid JSON response: {str(json_err)}", 
                            "raw_text": resp.text[:200]
                        }
                    
                    # Log the response
                    print(f"OpenAPI response status: {status_code}")
                    print(f"OPENAPI_BASE_URL_RISK: {OPENAPI_BASE_URL_RISK}")
                    
                    # Handle the case where the OpenAPI endpoint returns a specific error format
                    if not resp.is_success:
                        error_message = f"OpenAPI returned status code {status_code}"
                        # If the response contains the specific error format from OpenAPI
                        if isinstance(response_json, dict) and response_json.get('success') is False:
                            error_message += f": {response_json.get('message')} (code: {response_json.get('error')})"
                            # We'll store this error response in the database but won't raise an exception
                            print(f"OpenAPI error: {error_message}")
                        else:
                            # For other unsuccessful status codes, log but don't raise yet
                            print(f"HTTP error: {error_message}")
                except httpx.HTTPError as e:
                    # For connection errors and other non-response exceptions
                    status_code = getattr(e, "response", httpx.Response(status_code=502)).status_code
                    response_json = {"error": f"Connection error: {str(e)}"}
                    print(f"HTTP connection error: {str(e)}")
                except Exception as e:
                    # For other exceptions during the request
                    status_code = 500
                    response_json = {"error": f"Request error: {str(e)}"}
                    print(f"General request error: {str(e)}")
    except Exception as e:
        # Handle any other exceptions
        status_code = 500
        response_json = {"error": str(e)}
        print(f"Outer exception: {str(e)}")
    
    # Case 3: update=true and record exists - set existing to NOT ACTIVE and create new
    if update and existing_response:
        # Set existing record to NOT ACTIVE
        existing_response.status = "NOT ACTIVE"
        db.add(existing_response)
        db.commit()
    
    # Create new ACTIVE record (either for update=true or no existing record)
    new_record = models.CreditScoreResponse(
        identifier=identifier,
        response_json=response_json,
        status_code=status_code,
        status="ACTIVE"
    )
    db.add(new_record)
    db.commit()
    db.refresh(new_record)
    return new_record

@router.get("/company-full/{identifier}")  # Completely remove response_model instead of setting to None
async def get_company_full_data(
    identifier: str = Path(..., description="VAT code or tax code of the company to fetch full data for"),
    update: bool = Query(
        False, 
        description="When true, forces a fetch from OpenAPI and creates a new record; when false (default), returns existing record or creates a new request"
    ),
    email_callback: str = Query(
        None,
        description="Email address to notify when data is ready. If not provided, uses the default from settings."
    ),
    db: Session = Depends(database.get_db),
    request: Request = None
):
    """
    Fetch or update full company data from the OpenAPI source.
    
    ## Description
    This endpoint provides comprehensive company information including over 400 financial details.
    
    ## Behavior
    - If `update=false` (default):
      - If an ACTIVE completed record exists: Returns the existing record from the database
      - If a PENDING record exists: Returns the pending record (data is being fetched asynchronously)
      - If no record exists: Creates a new request to OpenAPI and returns PENDING status
    
    - If `update=true`:
      - All ACTIVE records for this identifier are marked as NOT ACTIVE
      - Creates a new request to OpenAPI and returns PENDING status
    
    ## Response
    - For COMPLETED records: Returns only the "data" field from the callback_json with company details
      (vatCode, taxCode, companyName, etc.) wrapped in a "data" root key
    - For PENDING records: Returns a simplified response with state and ID in a "data" root key
    - For new requests: Returns a simplified response with state and ID in a "data" root key
    
    ## Example Usage
    - Get cached data: `GET /company-full/ABC123`
    - Force refresh: `GET /company-full/ABC123?update=true`
    
    ## Note
    This is an asynchronous endpoint. The first call will initiate the data retrieval process,
    and you may need to poll the endpoint until the status changes from PENDING to COMPLETED.
    """
    # Generate a random session ID for this request
    import uuid
    import random
    import string
    
    # Either create a UUID or a random string
    session_id = f"bflows_{uuid.uuid4().hex[:16]}"
    
    # Get the base URL for callback
    base_url = str(request.base_url).rstrip('/')
    callback_url = f"{base_url}/webhook/company-full"
    
    # First, check for an existing ACTIVE and COMPLETED record
    if not update:
        existing_record = db.query(models.CompanyFullData).filter(
            models.CompanyFullData.identifier == identifier,
            models.CompanyFullData.status == "COMPLETED",
            models.CompanyFullData.version_status == "ACTIVE"
        ).order_by(models.CompanyFullData.created_at.desc()).first()
        
        # If we have a completed record, return the data field from callback_json wrapped with "data" as root key
        if existing_record:
            # Extract the data field from callback_json
            if existing_record and existing_record.callback_json and "data" in existing_record.callback_json:
                # Wrap the content in a {"data": ...} structure to ensure "data" is the root key
                return {"data": existing_record.callback_json["data"]}
            return existing_record
    
    # Next, check for PENDING requests (unless update=true)
    if not update:
        pending_record = db.query(models.CompanyFullData).filter(
            models.CompanyFullData.identifier == identifier,
            models.CompanyFullData.status == "PENDING",
            models.CompanyFullData.version_status == "ACTIVE"
        ).order_by(models.CompanyFullData.created_at.desc()).first()
        
        # If we have a pending record, return a simplified response with state and ID
        if pending_record:
            # Create a simplified response with just the state and ID
            return {
                "data": {
                    "state": "PENDING",
                    "id": pending_record.external_id or str(pending_record.id),
                    "message": "Riprova fra qualche minuto!"
                }
            }
    
    # If we get here, we need to create a new request
    
    # If update is true, we need to mark existing active records as inactive
    if update:
        existing_records = db.query(models.CompanyFullData).filter(
            models.CompanyFullData.identifier == identifier,
            models.CompanyFullData.version_status == "ACTIVE"
        ).all()
        
        for record in existing_records:
            record.version_status = "NOT ACTIVE"
            db.add(record)
        
        db.commit()
    
    # Create a new request to OpenAPI
    url = f"{OPENAPI_BASE_URL_COMPANY}/IT-full/{identifier}"
    
    # Create the callback configuration
    callback_config = {
        "url": callback_url,
        "method": "JSON",  # As specified in the requirements
        "headers": {
            "session_id": session_id
        }
    }
    
    # Prepare the payload for OpenAPI
    payload = {
        "callback": callback_config
    }
    
    # Log the request details
    print("=" * 40)
    print(f"Making POST request to OpenAPI company endpoint: {url}")
    print(f"Payload for OpenAPI:")
    print(json.dumps(payload, indent=2))
    print("=" * 40)
    
    status_code = 500
    response_json = {}
    
    try:
        # Make the request to OpenAPI
        async with httpx.AsyncClient() as client:
            headers = get_auth_headers_company()
            headers["accept"] = "application/json"
            headers["Content-Type"] = "application/json"
            
            # Log headers without exposing token
            headers_log = headers.copy()
            if "Authorization" in headers_log:
                headers_log["Authorization"] = "Bearer [REDACTED]"
            print(f"Request headers: {headers_log}")
            
            # Make the POST request to OpenAPI
            resp = await client.post(url, json=payload, headers=headers)
            status_code = resp.status_code
            
            # Log the response
            print(f"OpenAPI response status code: {status_code}")
            print(f"OpenAPI response headers: {dict(resp.headers)}")
            
            try:
                response_text = resp.text
                print(f"OpenAPI response text: {response_text[:500]}")  # Print only first 500 chars
                response_json = resp.json()
                print(f"OpenAPI response JSON: {json.dumps(response_json, indent=2)}")
            except Exception as e:
                print(f"Failed to parse response as JSON: {str(e)}")
                response_json = {"error": "Invalid JSON response"}
            
            resp.raise_for_status()
            
            # Extract external ID from the response (if available)
            external_id = response_json.get('data', {}).get('id', None)
            
        # Create the database record
        try:
            db_record = models.CompanyFullData(
                identifier=identifier,
                external_id=external_id,
                status="PENDING",
                version_status="ACTIVE",
                request_json=payload,
                response_json=response_json,
                email_callback=email_callback,  # Save the email for notification
                status_code=status_code
            )
        except Exception as e:
            # Fallback if email_callback column doesn't exist yet
            print(f"Warning: Could not set email_callback (column might not exist): {str(e)}")
            db_record = models.CompanyFullData(
                identifier=identifier,
                external_id=external_id,
                status="PENDING",
                version_status="ACTIVE",
                request_json=payload,
                response_json=response_json,
                status_code=status_code
            )
            
            db.add(db_record)
            db.commit()
            db.refresh(db_record)
            
            # Return a simplified response with state and ID for the newly created record
            return {
                "data": {
                    "state": "PENDING",
                    "id": external_id or str(db_record.id),
                    "message": "Riprova fra qualche minuto!"
                }
            }
    
    except httpx.HTTPError as e:
        # Handle HTTP errors from the API
        status_code = getattr(e, "response", httpx.Response(status_code=500)).status_code
        response_json = {"error": f"Connection error: {str(e)}"}
        error_detail = f"OpenAPI request failed: {str(e)}"
        
        try:
            if hasattr(e, "response") and e.response:
                error_json = e.response.json()
                if error_json.get('message'):
                    error_detail = error_json.get('message')
                    response_json = error_json
        except:
            pass
        
        # Create error record in the database
        db_record = models.CompanyFullData(
            identifier=identifier,
            status="ERROR",
            version_status="ACTIVE",
            request_json=payload,
            response_json=response_json,
            status_code=status_code
        )
        
        db.add(db_record)
        db.commit()
        db.refresh(db_record)
        
        raise HTTPException(status_code=status_code, detail=error_detail)
    
    except Exception as e:
        # Handle any other exceptions
        response_json = {"error": str(e)}
        
        # Create error record in the database
        db_record = models.CompanyFullData(
            identifier=identifier,
            status="ERROR",
            version_status="ACTIVE",
            request_json=payload,
            response_json=response_json,
            status_code=500
        )
        
        db.add(db_record)
        db.commit()
        db.refresh(db_record)
        
        raise HTTPException(status_code=500, detail=f"Failed to create company data request: {str(e)}")

@router.get("/negative-event")  # Completely remove response_model instead of setting to None
async def get_negative_event(
    cf_piva: str = Query(..., description="Tax code or VAT number to check for negative events"),
    update: bool = Query(
        False, 
        description="When true, forces a new request and marks old ones as inactive"
    ),
    email_callback: str = Query(
        None,
        description="Email address to notify when data is ready. If not provided, uses the default from settings."
    ),
    db: Session = Depends(database.get_db),
    request: Request = None
):
    """
    Get or initiate a check for negative events for a tax code or VAT number.
    
    ## Description
    This endpoint provides a unified interface for checking negative events.
    
    ## Behavior
    - If an ACTIVE completed request exists: Returns the existing record with details
    - If a PENDING request exists: Returns status that the request is still processing
    - If no request exists: Creates a new request to OpenAPI and returns PENDING status
    
    ## Parameters
    - cf_piva: Tax code or VAT number to check (query parameter)
    - update: When true, creates a new request even if an existing one is found
    
    ## Response
    - For COMPLETED records: Returns the detail_json content directly from the negativa_details table
    - For PENDING records: Returns a simplified response with state, cf_piva, and message in a "data" root key
    - For new requests: Returns a simplified response with state, cf_piva, and message in a "data" root key
    
    ## Example Usage
    - Get cached data: `GET /negative-event?cf_piva=ABC123`
    - Force refresh: `GET /negative-event?cf_piva=ABC123&update=true`
    """
    # Generate a random session ID for this request
    import uuid
    import random
    import string
    
    # Either create a UUID or a random string
    session_id = f"bflows_{uuid.uuid4().hex[:16]}"
    
    # Get the base URL for callback
    base_url = str(request.base_url).rstrip('/')
    callback_url = f"{base_url}/webhook/negative-event"
    
    # First, check for an existing ACTIVE and COMPLETED record
    if not update:
        existing_request = db.query(models.NegativaRequest).filter(
            models.NegativaRequest.cf_piva == cf_piva,
            models.NegativaRequest.status == "COMPLETED",
            models.NegativaRequest.version_status == "ACTIVE"
        ).order_by(models.NegativaRequest.created_at.desc()).first()
        
        # If we have a completed record, return the detail_json content from negativa_details
        if existing_request:
            # Get the details
            details = db.query(models.NegativaDetail).filter(
                models.NegativaDetail.request_id == existing_request.id
            ).first()
            
            # Return the detail_json content directly
            if details and hasattr(details, 'detail_json'):
                return details.detail_json
            
            # Fallback if detail_json is not available
            return {
                "request": existing_request,
                "detail": details
            }
    
    # Next, check for PENDING requests (unless update=true)
    if not update:
        pending_request = db.query(models.NegativaRequest).filter(
            models.NegativaRequest.cf_piva == cf_piva,
            models.NegativaRequest.status == "PENDING",
            models.NegativaRequest.version_status == "ACTIVE"
        ).order_by(models.NegativaRequest.created_at.desc()).first()
        
        # If we have a pending request, return a simplified response with standardized format
        if pending_request:
            return {
                "data": {
                    "state": "PENDING",
                    "cf_piva": pending_request.cf_piva,
                    "message": "Riprova fra qualche minuto!"
                }
            }
    
    # If we get here, we need to create a new request
    
    # If update is true, we need to mark existing active records as inactive
    if update:
        existing_records = db.query(models.NegativaRequest).filter(
            models.NegativaRequest.cf_piva == cf_piva,
            models.NegativaRequest.version_status == "ACTIVE"
        ).all()
        
        for record in existing_records:
            record.version_status = "NOT ACTIVE"
            db.add(record)
        
        db.commit()
    
    # Create a new request to OpenAPI
    url = f"{OPENAPI_BASE_URL_RISK}/IT-negativita"
    
    # Create the callback configuration
    callback_config = {
        "url": callback_url,
        "method": "POST",
        "field": "data",
        "headers": {
            "session_id": session_id
        }
    }
    
    # Prepare the payload for OpenAPI in the exact format they expect
    payload = {
        "cf_piva": cf_piva,
        "callback": callback_config
    }
    
    # Log the request details
    print("=" * 40)
    print(f"Making POST request to OpenAPI endpoint: {url}")
    print(f"Payload for OpenAPI:")
    print(json.dumps(payload, indent=2))
    print("=" * 40)
    
    try:
        # Make the request to OpenAPI
        async with httpx.AsyncClient() as client:
            headers = get_auth_headers_risk()
            headers["accept"] = "application/json"
            headers["Content-Type"] = "application/json"
            
            # Log headers without exposing token
            headers_log = headers.copy()
            if "Authorization" in headers_log:
                headers_log["Authorization"] = "Bearer [REDACTED]"
            print(f"Request headers: {headers_log}")
            
            # Make the POST request to OpenAPI
            resp = await client.post(url, json=payload, headers=headers)
            
            # Log the response
            print(f"OpenAPI response status code: {resp.status_code}")
            print(f"OpenAPI response headers: {dict(resp.headers)}")
            
            try:
                response_text = resp.text
                print(f"OpenAPI response text: {response_text[:500]}")  # Print only first 500 chars to avoid cluttering logs
                response_json = resp.json()
                print(f"OpenAPI response JSON: {json.dumps(response_json, indent=2)}")
            except Exception as e:
                print(f"Failed to parse response as JSON: {str(e)}")
                response_json = {"error": "Invalid JSON response"}
            
            resp.raise_for_status()
            
            # Extract external ID from the response
            external_id = response_json.get('data', {}).get('id')
            
            if not external_id:
                raise HTTPException(status_code=500, detail="Invalid response from OpenAPI: missing ID")
            
            # Create the database record
            try:
                db_request = models.NegativaRequest(
                    external_id=external_id,
                    cf_piva=cf_piva,
                    status="PENDING",
                    version_status="ACTIVE",
                    request_json=payload,  # Store the actual payload we sent
                    response_json=response_json,
                    email_callback=email_callback  # Save the email for notification
                )
            except Exception as e:
                # Fallback if email_callback column doesn't exist yet
                print(f"Warning: Could not set email_callback (column might not exist): {str(e)}")
                db_request = models.NegativaRequest(
                    external_id=external_id,
                    cf_piva=cf_piva,
                    status="PENDING",
                    version_status="ACTIVE",
                    request_json=payload,  # Store the actual payload we sent
                    response_json=response_json
                )
            
            db.add(db_request)
            db.commit()
            db.refresh(db_request)
            
            # Return a simplified response with state and ID for the newly created record
            return {
                "data": {
                    "state": "PENDING",
                    "cf_piva": cf_piva,
                    "message": "Riprova fra qualche minuto!"
                }
            }
    
    except httpx.HTTPError as e:
        # Handle HTTP errors from the API
        status_code = getattr(e, "response", httpx.Response(status_code=500)).status_code
        error_detail = f"OpenAPI request failed: {str(e)}"
        
        try:
            if hasattr(e, "response") and e.response:
                error_json = e.response.json()
                if error_json.get('message'):
                    error_detail = error_json.get('message')
        except:
            pass
        
        raise HTTPException(status_code=status_code, detail=error_detail)
    
    except Exception as e:
        # Handle any other exceptions
        raise HTTPException(status_code=500, detail=f"Failed to create negative event request: {str(e)}")

# Background task to fetch negative event details
async def fetch_negative_detail(request_id: int, external_id: str, db: Session):
    """Background task to fetch details for a negative event after callback"""
    print(f"=== BACKGROUND TASK: fetch_negative_detail started for request_id={request_id}, external_id={external_id} ===")
    
    # Get the request from the database
    db_request = db.query(models.NegativaRequest).filter(
        models.NegativaRequest.id == request_id
    ).first()
    
    if not db_request:
        print(f"Error: Request {request_id} not found")
        return
    
    # Call the detail endpoint
    url = f"{OPENAPI_BASE_URL_RISK}/IT-negativita/{external_id}/dettaglio"
    print(f"Making GET request to OpenAPI details endpoint: {url}")
    
    try:
        headers = get_auth_headers_risk()
        headers["accept"] = "application/json"
        
        # Log headers without exposing token
        headers_log = headers.copy()
        if "Authorization" in headers_log:
            headers_log["Authorization"] = "Bearer [REDACTED]"
        print(f"Request headers: {headers_log}")
        
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers, timeout=30.0)
            status_code = resp.status_code
            
            print(f"OpenAPI details response status code: {status_code}")
            print(f"OpenAPI details response headers: {dict(resp.headers)}")
            
            try:
                response_text = resp.text
                print(f"OpenAPI details response text: {response_text[:500]}...")  # Print first 500 chars
                detail_json = resp.json()
                print(f"OpenAPI details response JSON: {json.dumps(detail_json, indent=2)}")
            except Exception as json_err:
                print(f"Failed to parse response as JSON: {str(json_err)}")
                # If we can't parse the response, create a minimal error detail
                detail_json = {"error": f"Invalid JSON response: {str(json_err)}"}
                # Still continue to save what we can
            
            resp.raise_for_status()
            
            # Create or update the detail record
            detail = db.query(models.NegativaDetail).filter(
                models.NegativaDetail.request_id == request_id
            ).first()
            
            # Extract presence flags (with defaults if missing)
            presence_pregiudizievoli = detail_json.get('data', {}).get('presenzaPregiudizievoli', False)
            presence_procedure = detail_json.get('data', {}).get('presenzaProcedure', False)
            presence_protesti = detail_json.get('data', {}).get('presenzaProtesti', False)
            
            print(f"Extracted flags: pregiudizievoli={presence_pregiudizievoli}, " + 
                  f"procedure={presence_procedure}, protesti={presence_protesti}")
            
            if detail:
                print(f"Updating existing detail record id={detail.id}")
                # Update existing detail
                detail.detail_json = detail_json
                detail.status_code = status_code
                detail.presence_pregiudizievoli = presence_pregiudizievoli
                detail.presence_procedure = presence_procedure
                detail.presence_protesti = presence_protesti
            else:
                print(f"Creating new detail record for request_id={request_id}")
                # Create new detail
                detail = models.NegativaDetail(
                    request_id=request_id,
                    detail_json=detail_json,
                    status_code=status_code,
                    presence_pregiudizievoli=presence_pregiudizievoli,
                    presence_procedure=presence_procedure,
                    presence_protesti=presence_protesti
                )
                db.add(detail)
            
            # Update the request status
            db_request.status = "COMPLETED"
            db.add(db_request)
            db.commit()
            print(f"Detail saved and request status updated to COMPLETED")
    
    except Exception as e:
        print(f"Error fetching negative event detail: {str(e)}")
        # Update the request status to indicate error
        db_request.status = "ERROR"
        db.add(db_request)
        db.commit()
        print(f"Request status updated to ERROR")
    
    print("=== BACKGROUND TASK: fetch_negative_detail completed ===")

# This route will NOT be shown in Swagger docs - Callback for negative events
@router.post("/webhook/negative-event", include_in_schema=False, status_code=200)
async def negative_event_callback(
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(database.get_db)
):
    """
    Webhook endpoint to receive callbacks from OpenAPI after a negative event check is complete.
    This endpoint is not exposed in the public API documentation.
    """
    # Always respond with a success even if we have problems
    # This prevents the OpenAPI service from retrying and creating duplicate records
    response_data = {"message": "Callback received", "success": True}
    
    try:
        # Log webhook call details
        print("=" * 60)
        print(f"WEBHOOK CALLED: /webhook/negative-event at {request.url}")
        print(f"Client IP: {request.client.host if request.client else 'Unknown'}")
        print(f"Request headers: {dict(request.headers)}")
        
        # Get raw request data
        raw_body = await request.body()
        print(f"Raw body (bytes): {raw_body}")
        
        # Try all possible ways to extract data from the request
        callback_data = {}
        
        # 1. Try to parse as JSON
        try:
            body_json = await request.json()
            print(f"Successfully parsed as JSON: {json.dumps(body_json, indent=2)}")
            callback_data.update(body_json)
        except Exception as e:
            print(f"Not valid JSON: {str(e)}")
        
        # 2. Try to parse as form data
        try:
            body_form = await request.form()
            if body_form:
                form_dict = dict(body_form)
                print(f"Successfully parsed as form: {form_dict}")
                callback_data.update(form_dict)
        except Exception as e:
            print(f"Not valid form data: {str(e)}")
        
        # 3. Try to parse as plain text
        try:
            body_text = raw_body.decode('utf-8', errors='replace')
            print(f"Body as text: {body_text}")
            if body_text and not callback_data:
                # Handle the special case from OpenAPI - data parameter with URL-encoded JSON
                if body_text.startswith('data='):
                    try:
                        from urllib.parse import unquote
                        # URL-decode the data parameter
                        json_str = unquote(body_text[5:])  # Remove 'data=' and unquote
                        print(f"URL-decoded JSON string: {json_str}")
                        # Parse the JSON
                        parsed_json = json.loads(json_str)
                        print(f"Successfully parsed URL-encoded JSON: {parsed_json}")
                        callback_data.update(parsed_json)
                        
                        # If the data is nested inside a 'data' key, extract it
                        if 'data' in parsed_json and isinstance(parsed_json['data'], dict):
                            # Add the nested data with prefixed keys for easy access
                            for key, value in parsed_json['data'].items():
                                callback_data[f"data_{key}"] = value
                            print(f"Extracted nested data from 'data' field")
                    except Exception as e:
                        print(f"Failed to parse URL-encoded JSON: {str(e)}")
                # If it looks like a form but wasn't parsed
                elif '=' in body_text and '&' in body_text:
                    try:
                        from urllib.parse import parse_qs
                        form_data = parse_qs(body_text)
                        text_dict = {k: v[0] if len(v) == 1 else v for k, v in form_data.items()}
                        print(f"Parsed as form string: {text_dict}")
                        callback_data.update(text_dict)
                        
                                        # If there's a 'data' parameter containing JSON
                        if 'data' in text_dict:
                            try:
                                data_json = json.loads(text_dict['data'])
                                print(f"Parsed 'data' parameter as JSON: {data_json}")
                                callback_data['data_parsed'] = data_json
                                
                                # Extract all fields from the 'data' parameter
                                # First add data_json to callback_data
                                for key, value in data_json.items():
                                    callback_data[f"data_{key}"] = value
                                
                                # Then specifically handle nested 'data' object if present
                                if 'data' in data_json and isinstance(data_json['data'], dict):
                                    inner_data = data_json['data']
                                    print(f"Found inner data object: {inner_data}")
                                    
                                    # Add all inner data fields with data_inner_ prefix
                                    for key, value in inner_data.items():
                                        callback_data[f"data_inner_{key}"] = value
                                    
                                    # Special handling for ID field
                                    if 'id' in inner_data:
                                        callback_data['id'] = inner_data['id']
                                        print(f"Extracted ID from inner data: {inner_data['id']}")
                            except Exception as e:
                                print(f"Failed to parse 'data' parameter as JSON: {str(e)}")
                    except Exception as e:
                        print(f"Failed to parse as form string: {str(e)}")
                elif body_text.strip().startswith('{') and body_text.strip().endswith('}'):
                    try:
                        # Try one more time to parse as JSON
                        text_json = json.loads(body_text)
                        print(f"Parsed text as JSON: {text_json}")
                        callback_data.update(text_json)
                    except Exception as e:
                        print(f"Failed to parse text as JSON: {str(e)}")
                else:
                    callback_data["raw_text"] = body_text
        except Exception as e:
            print(f"Error decoding body as text: {str(e)}")
        
        # 4. Add all headers to the data dictionary
        headers_dict = {f"header_{k.lower().replace('-', '_')}": v for k, v in request.headers.items()}
        print(f"Adding headers to data: {headers_dict}")
        callback_data.update(headers_dict)
        
        # 5. Extract session_id from headers if present
        if "session-id" in request.headers:
            callback_data["session_id"] = request.headers.get("session-id")
            print(f"Found session_id in headers: {callback_data['session_id']}")
        elif "x-session-id" in request.headers:
            callback_data["session_id"] = request.headers.get("x-session-id")
            print(f"Found x-session-id in headers: {callback_data['session_id']}")
        
        print(f"Final callback data dictionary: {callback_data}")
        print("=" * 60)
        
        # Extract the ID and status from the callback data with many fallbacks
        external_id = None
        status = None
        
        # Try all possible keys for external_id
        for id_key in ['id', 'external_id', 'request_id', 'data.id', 'data_id', 'data_inner_id']:
            if id_key in callback_data:
                external_id = callback_data[id_key]
                print(f"Found external_id in field {id_key}: {external_id}")
                break
            elif '.' in id_key:
                # Try nested key like "data.id"
                parent, child = id_key.split('.', 1)
                if parent in callback_data and isinstance(callback_data[parent], dict) and child in callback_data[parent]:
                    external_id = callback_data[parent][child]
                    print(f"Found external_id in nested field {id_key}: {external_id}")
                    break
                
        # Special check for data field containing JSON with 'data.id' 
        if not external_id and 'data' in callback_data and isinstance(callback_data['data'], str):
            try:
                # Try to parse the 'data' string as JSON
                nested_json = json.loads(callback_data['data'])
                
                # Check for inner data structure
                if 'data' in nested_json and isinstance(nested_json['data'], dict):
                    inner_data = nested_json['data']
                    
                    # Check for ID in the inner data
                    if 'id' in inner_data:
                        external_id = inner_data['id']
                        print(f"Found external_id in nested JSON data field: {external_id}")
                        
                        # Also store the data object for future use
                        callback_data['data_parsed'] = nested_json
                        
                        # Add inner data fields with prefix
                        for key, value in inner_data.items():
                            callback_data[f"data_inner_{key}"] = value
            except Exception as e:
                print(f"Failed to extract ID from data field: {str(e)}")
        
        # Try all possible header keys for external_id
        for header_key in ['x-callback-id', 'x-request-id', 'x-external-id']:
            if not external_id and header_key in request.headers:
                external_id = request.headers.get(header_key)
                print(f"Found external_id in header {header_key}: {external_id}")
                break
        
        # Try all possible keys for status
        for status_key in ['status', 'state', 'result', 'data.status', 'data_status']:
            if status_key in callback_data:
                status = callback_data[status_key]
                print(f"Found status in field {status_key}: {status}")
                break
            elif '.' in status_key:
                # Try nested key like "data.status"
                parent, child = status_key.split('.', 1)
                if parent in callback_data and isinstance(callback_data[parent], dict) and child in callback_data[parent]:
                    status = callback_data[parent][child]
                    print(f"Found status in nested field {status_key}: {status}")
                    break
        
        # Try all possible header keys for status
        for header_key in ['x-callback-status', 'x-status', 'x-state']:
            if not status and header_key in request.headers:
                status = request.headers.get(header_key)
                print(f"Found status in header {header_key}: {status}")
                break
            
        print(f"Processing webhook: external_id={external_id}, status={status}")
        
        if not external_id:
            # Instead of raising an exception, log the error and return a success response
            print("WARNING: Missing ID in callback data, but returning success to prevent retries")
            response_data["warning"] = "Missing ID in callback data"
            return response_data
        
        # Try to find the corresponding request in the database
        db_request = db.query(models.NegativaRequest).filter(
            models.NegativaRequest.external_id == external_id
        ).first()
        
        if not db_request:
            # Instead of raising an exception, log the error and return a success response
            print(f"WARNING: Request with external ID {external_id} not found, but returning success")
            response_data["warning"] = f"Request with external ID {external_id} not found"
            return response_data
        
        # Update the request with callback data
        db_request.callback_json = callback_data
        if status:
            db_request.status = status
        db.add(db_request)
        db.commit()
        
        # Launch background task to fetch details
        background_tasks.add_task(fetch_negative_detail, db_request.id, external_id, db)
        
        # Send email notification if email_callback is set
        try:
            if hasattr(db_request, 'email_callback') and db_request.email_callback:
                # Prepare notification data
                notification_data = {
                    "cf_piva": db_request.cf_piva,
                    "status": db_request.status,
                    "id": external_id
                }
                
                # Include any additional data available in callback data
                if 'data_inner_esito' in callback_data:
                    notification_data["result"] = callback_data['data_inner_esito']
                
                # Send the notification
                email_utils.send_callback_notification(
                    db_request.email_callback,
                    "negative-event",
                    db_request.cf_piva,
                    notification_data
                )
                print(f"Email notification sent to {db_request.email_callback}")
        except Exception as e:
            print(f"Failed to send email notification: {str(e)}")
        
        # Add request ID to response
        response_data["request_id"] = db_request.id
        print(f"Webhook successful, returning: {response_data}")
        
        # Return success
        return response_data
    
    except Exception as e:
        # Even if we have an internal error, return a success response to prevent OpenAPI from retrying
        print(f"ERROR in webhook processing: {str(e)}")
        response_data["warning"] = f"Internal error occurred, but accepting callback: {str(e)}"
        return response_data

@router.get("/company-all-data")
async def get_company_all_data(
    identifier: str = Query(..., description="VAT code, tax code, or company ID to fetch all data for"),
    update: bool = Query(
        False, 
        description="When true, forces a fetch from OpenAPI for all endpoints and creates new records"
    ),
    email_callback: str = Query(
        None,
        description="Email address to notify when data is ready. If not provided, uses the default from settings."
    ),
    db: Session = Depends(database.get_db),
    request: Request = None
):
    """
    Fetch comprehensive data from all available endpoints in a single call.
    
    ## Description
    This endpoint combines the results from credit-score, company-full, and negative-event endpoints
    into a single response with three keys.
    
    ## Behavior
    - Calls each endpoint (credit-score, company-full, and negative-event) with the provided identifier
    - Returns a combined response with data from all three sources
    
    ## Parameters
    - identifier: VAT code, tax code, or company ID to use for all requests
    - update: When true, forces a fresh fetch for all endpoints
    - email_callback: Optional email address to receive notifications when asynchronous data is ready
    
    ## Response
    Returns a JSON object with three keys:
    - credit_score: The response from the credit-score endpoint
    - company_data: The response from the company-full endpoint
    - negative_events: The response from the negative-event endpoint
    
    ## Example Usage
    - Get all cached data: `GET /company-all-data?identifier=ABC123`
    - Force refresh of all data: `GET /company-all-data?identifier=ABC123&update=true`
    """
    # Create a dictionary to store the combined results
    combined_results = {}
    
    # Get credit score data
    try:
        credit_score = await get_credit_score(identifier=identifier, update=update, db=db)
        # Convert Pydantic model to dict if needed
        if hasattr(credit_score, "dict"):
            combined_results["credit_score"] = credit_score.dict()
        else:
            combined_results["credit_score"] = credit_score
    except Exception as e:
        combined_results["credit_score"] = {"error": str(e)}
    
    # Get company full data
    try:
        company_data = await get_company_full_data(identifier=identifier, update=update, db=db, request=request)
        combined_results["company_data"] = company_data
    except Exception as e:
        combined_results["company_data"] = {"error": str(e)}
    
    # Get negative event data
    try:
        # For negative-event, we need to use the cf_piva parameter name
        negative_events = await get_negative_event(cf_piva=identifier, update=update, db=db, request=request)
        combined_results["negative_events"] = negative_events
    except Exception as e:
        combined_results["negative_events"] = {"error": str(e)}
    
    return combined_results

# This route will NOT be shown in Swagger docs - Callback for company full data
@router.post("/webhook/company-full", include_in_schema=False, status_code=200)
async def company_full_callback(
    request: Request,
    db: Session = Depends(database.get_db)
):
    """
    Webhook endpoint to receive callbacks from OpenAPI after a company full data request is complete.
    This endpoint is not exposed in the public API documentation.
    """
    # Always respond with a success to prevent retries
    response_data = {"message": "Company data callback received", "success": True}
    
    try:
        # Log webhook call details
        print("=" * 60)
        print(f"WEBHOOK CALLED: /webhook/company-full at {request.url}")
        print(f"Client IP: {request.client.host if request.client else 'Unknown'}")
        print(f"Request headers: {dict(request.headers)}")
        
        # Get raw request data
        raw_body = await request.body()
        print(f"Raw body (bytes): {raw_body}")
        
        # Try all possible ways to extract data from the request
        callback_data = {}
        
        # 1. Try to parse as JSON
        try:
            body_json = await request.json()
            print(f"Successfully parsed as JSON: {json.dumps(body_json, indent=2)}")
            callback_data.update(body_json)
        except Exception as e:
            print(f"Not valid JSON: {str(e)}")
        
        # 2. Try to parse as form data
        try:
            body_form = await request.form()
            if body_form:
                form_dict = dict(body_form)
                print(f"Successfully parsed as form: {form_dict}")
                callback_data.update(form_dict)
        except Exception as e:
            print(f"Not valid form data: {str(e)}")
        
        # 3. Try to parse as plain text
        try:
            body_text = raw_body.decode('utf-8', errors='replace')
            print(f"Body as text: {body_text}")
            if body_text and not callback_data:
                # Handle the special case from OpenAPI - data parameter with URL-encoded JSON
                if body_text.startswith('data='):
                    try:
                        from urllib.parse import unquote
                        # URL-decode the data parameter
                        json_str = unquote(body_text[5:])  # Remove 'data=' and unquote
                        print(f"URL-decoded JSON string: {json_str}")
                        # Parse the JSON
                        parsed_json = json.loads(json_str)
                        print(f"Successfully parsed URL-encoded JSON: {parsed_json}")
                        callback_data.update(parsed_json)
                    except Exception as e:
                        print(f"Failed to parse URL-encoded JSON: {str(e)}")
                # If it looks like a form but wasn't parsed
                elif '=' in body_text and '&' in body_text:
                    try:
                        from urllib.parse import parse_qs
                        form_data = parse_qs(body_text)
                        text_dict = {k: v[0] if len(v) == 1 else v for k, v in form_data.items()}
                        print(f"Parsed as form string: {text_dict}")
                        callback_data.update(text_dict)
                    except Exception as e:
                        print(f"Failed to parse as form string: {str(e)}")
                elif body_text.strip().startswith('{') and body_text.strip().endswith('}'):
                    try:
                        # Try one more time to parse as JSON
                        text_json = json.loads(body_text)
                        print(f"Parsed text as JSON: {text_json}")
                        callback_data.update(text_json)
                    except Exception as e:
                        print(f"Failed to parse text as JSON: {str(e)}")
                else:
                    callback_data["raw_text"] = body_text
        except Exception as e:
            print(f"Error decoding body as text: {str(e)}")
        
        # 4. Add all headers to the data dictionary
        headers_dict = {f"header_{k.lower().replace('-', '_')}": v for k, v in request.headers.items()}
        print(f"Adding headers to data: {headers_dict}")
        callback_data.update(headers_dict)
        
        # Find session_id in headers (could be in different formats)
        session_id = None
        for key in request.headers.keys():
            if "session" in key.lower():
                session_id = request.headers.get(key)
                print(f"Found session ID in header {key}: {session_id}")
                break
        
        if not session_id and "header_session_id" in callback_data:
            session_id = callback_data["header_session_id"]
            print(f"Found session ID in callback data: {session_id}")
        
        # Extract the company ID from the callback data
        external_id = None
        status = "COMPLETED"  # Default status for company data
        
        # Try all possible locations for the external_id
        for id_key in ['id', 'data.id', 'request_id', 'company_id', 'identifier']:
            if id_key in callback_data:
                external_id = callback_data[id_key]
                print(f"Found external_id in field {id_key}: {external_id}")
                break
            elif '.' in id_key:
                parent, child = id_key.split('.', 1)
                if parent in callback_data and isinstance(callback_data[parent], dict) and child in callback_data[parent]:
                    external_id = callback_data[parent][child]
                    print(f"Found external_id in nested field {id_key}: {external_id}")
                    break
        
        # Skip external_id checks - it's not present in the callback data
        # We'll rely on the vatCode/taxCode to find the corresponding record
        
        # Extract vatCode or taxCode from the callback data
        vat_code = None
        tax_code = None
        try:
            if 'data' in callback_data and 'companyDetails' in callback_data['data']:
                company_details = callback_data['data']['companyDetails']
                vat_code = company_details.get('vatCode')
                tax_code = company_details.get('taxCode')
                print(f"Extracted vatCode: {vat_code}, taxCode: {tax_code}")
                
                # These can be used to find the corresponding record
                if vat_code or tax_code:
                    external_id = vat_code or tax_code
                    print(f"Using vatCode/taxCode as external_id: {external_id}")
        except Exception as e:
            print(f"Error extracting vatCode/taxCode: {str(e)}")
        
        # Find the corresponding record in the database
        # First, try by vatCode or taxCode (these should match the identifier used in the request)
        db_record = None
        identifier_to_match = vat_code or tax_code
        
        # Debug logging
        print(f"Looking for record with identifier={identifier_to_match}, external_id={external_id}")
        
        # First, try a more lenient search to find ANY pending record
        if not db_record:
            pending_records = db.query(models.CompanyFullData).filter(
                models.CompanyFullData.status == "PENDING",
                models.CompanyFullData.version_status == "ACTIVE"
            ).order_by(models.CompanyFullData.created_at.desc()).all()
            
            print(f"Found {len(pending_records)} pending records")
            
            # Try to match by identifier exactly
            if identifier_to_match:
                db_record = db.query(models.CompanyFullData).filter(
                    models.CompanyFullData.identifier == identifier_to_match,
                    models.CompanyFullData.version_status == "ACTIVE"
                ).order_by(models.CompanyFullData.created_at.desc()).first()
                
                if db_record:
                    print(f"Found record by identifier match: {identifier_to_match}")
            
            # If not found by identifier, try by external_id 
            if not db_record and external_id:
                db_record = db.query(models.CompanyFullData).filter(
                    models.CompanyFullData.external_id == external_id,
                    models.CompanyFullData.version_status == "ACTIVE"
                ).order_by(models.CompanyFullData.created_at.desc()).first()
                
                if db_record:
                    print(f"Found record by external_id: {external_id}")
                    
            # If still not found, try a fuzzy match on identifier
            if not db_record and identifier_to_match:
                for record in pending_records:
                    if record.identifier and identifier_to_match in record.identifier:
                        db_record = record
                        print(f"Found record by fuzzy identifier match: {record.identifier} contains {identifier_to_match}")
                        break
            
            # If still not found, just use the most recent pending record
            if not db_record and pending_records:
                db_record = pending_records[0]
                print(f"No exact match found, using most recent pending record with id={db_record.id}")
        
        # If still not found, try by session_id
        if not db_record and session_id:
            all_pending = db.query(models.CompanyFullData).filter(
                models.CompanyFullData.status == "PENDING",
                models.CompanyFullData.version_status == "ACTIVE"
            ).order_by(models.CompanyFullData.created_at.desc()).all()
            
            for record in all_pending:
                try:
                    req_json = record.request_json
                    if req_json and isinstance(req_json, dict) and 'callback' in req_json:
                        callback = req_json['callback']
                        if isinstance(callback, dict) and 'headers' in callback:
                            headers = callback['headers']
                            if isinstance(headers, dict) and 'session_id' in headers:
                                if headers['session_id'] == session_id:
                                    db_record = record
                                    print(f"Found record by session_id: {session_id}")
                                    break
                except Exception as e:
                    print(f"Error checking record for session_id: {str(e)}")
        
        # If no record is found, log all active records in the database for debugging
        if not db_record:
            all_records = db.query(models.CompanyFullData).filter(
                models.CompanyFullData.version_status == "ACTIVE"
            ).all()
            
            print(f"DEBUG: Found {len(all_records)} ACTIVE records in total")
            for record in all_records:
                print(f"DEBUG: Record id={record.id}, identifier={record.identifier}, status={record.status}")
            
            # If there's any data available, create a new record with it
            if vat_code or tax_code:
                identifier = vat_code or tax_code
                
                print(f"Creating new record for identifier={identifier} since no pending record was found")
                db_record = models.CompanyFullData(
                    identifier=identifier,
                    external_id=external_id,
                    status="COMPLETED",
                    version_status="ACTIVE",
                    callback_json=callback_data
                )
                
                db.add(db_record)
                db.commit()
                db.refresh(db_record)
                
                print(f"Successfully created new record with id={db_record.id}")
            else:
                print(f"WARNING: No pending company data record found for external_id={external_id}")
                response_data["warning"] = f"No pending record found for external_id={external_id}"
                return response_data
        
        # Update the record with the callback data
        db_record.callback_json = callback_data
        db_record.status = status
        
        # Extract the identifier from callback data if it's available and our record has none
        if not db_record.identifier and "identifier" in callback_data:
            db_record.identifier = callback_data["identifier"]
        
        db.add(db_record)
        db.commit()
        db.refresh(db_record)
        
        # Send email notification if email_callback is set
        try:
            if hasattr(db_record, 'email_callback') and db_record.email_callback:
                # Get identifier from the record
                identifier = db_record.identifier or external_id or "Unknown"
                
                # Extract some useful data for the notification
                notification_data = {
                    "identifier": identifier,
                    "status": status
                }
                
                # Include some company details in the notification if available
                if 'data' in callback_data and 'companyDetails' in callback_data['data']:
                    company_details = callback_data['data']['companyDetails']
                    if 'companyName' in company_details:
                        notification_data["companyName"] = company_details['companyName']
                    if 'vatCode' in company_details:
                        notification_data["vatCode"] = company_details['vatCode']
                    if 'taxCode' in company_details:
                        notification_data["taxCode"] = company_details['taxCode']
                
                # Send the notification
                email_utils.send_callback_notification(
                    db_record.email_callback,
                    "company-full",
                    identifier,
                    notification_data
                )
                print(f"Email notification sent to {db_record.email_callback}")
        except Exception as e:
            print(f"Failed to send email notification: {str(e)}")
        
        response_data["company_id"] = external_id
        response_data["request_id"] = db_record.id
        print(f"Successfully processed company data callback: {response_data}")
        
        return response_data
    except Exception as e:
        print(f"ERROR processing company data callback: {str(e)}")
        response_data["error"] = str(e)
        # Still return 200 OK to prevent retries
        return response_data
