from fastapi import APIRouter, Depends, HTTPException, Path, Query, BackgroundTasks, Request, Body
from sqlalchemy.orm import Session
from . import database, models, schemas
import httpx
import os
import json
from typing import Dict, Any, Optional
from fastapi.openapi.utils import get_openapi
from fastapi.routing import APIRoute

router = APIRouter(
    tags=["OpenAPI Proxy"]
)

OPENAPI_BASE_URL_RISK = os.getenv("OPENAPI_BASE_URL_RISK")
OPENAPI_TOKEN_RISK = os.getenv("OPENAPI_TOKEN_RISK")

# Headers with Bearer token authentication
def get_auth_headers():
    return {"Authorization": f"Bearer {OPENAPI_TOKEN_RISK}"}

@router.get("/credit-score/{identifier}", response_model=schemas.CreditScoreResponse)
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
    Returns a CreditScoreResponse object with:
    - Organization identifier
    - Complete credit score data in response_json
    - HTTP status code from the OpenAPI call
    - Record status (ACTIVE/NOT ACTIVE)
    - Timestamps for creation and updates
    
    ## Example Usage
    - Get cached data: `GET /credit-score/ABC123`
    - Force refresh: `GET /credit-score/ABC123?update=true`
    """
    # Check if we already have an ACTIVE record for this identifier
    existing_response = db.query(models.CreditScoreResponse).filter(
        models.CreditScoreResponse.identifier == identifier,
        models.CreditScoreResponse.status == "ACTIVE"
    ).first()
    
    # Case 1: update=false/not set and record exists - return the existing record
    if not update and existing_response:
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
                    headers = get_auth_headers()
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

@router.get("/negative-event", response_model=schemas.NegativaFullResponse)
async def get_negative_event(
    cf_piva: str = Query(..., description="Tax code or VAT number to check for negative events"),
    update: bool = Query(
        False, 
        description="When true, forces a new request and marks old ones as inactive"
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
    Returns a NegativaFullResponse object with:
    - Request information (status, timestamps, etc.)
    - Detail information if available (presence of negative events, etc.)
    - If the check is still pending, only basic request info is returned
    
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
        
        # If we have a completed record, return it with its details
        if existing_request:
            # Get the details
            details = db.query(models.NegativaDetail).filter(
                models.NegativaDetail.request_id == existing_request.id
            ).first()
            
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
        
        # If we have a pending request, return it without details
        if pending_request:
            return {
                "request": pending_request,
                "detail": None
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
            headers = get_auth_headers()
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
            
            # Return the new request
            return {
                "request": db_request,
                "detail": None
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
    # Get the request from the database
    db_request = db.query(models.NegativaRequest).filter(
        models.NegativaRequest.id == request_id
    ).first()
    
    if not db_request:
        print(f"Error: Request {request_id} not found")
        return
    
    # Call the detail endpoint
    url = f"{OPENAPI_BASE_URL_RISK}/IT-negativita/{external_id}/dettaglio"
    
    try:
        headers = get_auth_headers()
        headers["accept"] = "application/json"
        
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers)
            status_code = resp.status_code
            resp.raise_for_status()
            detail_json = resp.json()
            
            # Create or update the detail record
            detail = db.query(models.NegativaDetail).filter(
                models.NegativaDetail.request_id == request_id
            ).first()
            
            # Extract presence flags
            presence_pregiudizievoli = detail_json.get('data', {}).get('presenzaPregiudizievoli', False)
            presence_procedure = detail_json.get('data', {}).get('presenzaProcedure', False)
            presence_protesti = detail_json.get('data', {}).get('presenzaProtesti', False)
            
            if detail:
                # Update existing detail
                detail.detail_json = detail_json
                detail.status_code = status_code
                detail.presence_pregiudizievoli = presence_pregiudizievoli
                detail.presence_procedure = presence_procedure
                detail.presence_protesti = presence_protesti
            else:
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
    
    except Exception as e:
        print(f"Error fetching negative event detail: {str(e)}")
        # Update the request status to indicate error
        db_request.status = "ERROR"
        db.add(db_request)
        db.commit()

# This route will NOT be shown in Swagger docs
@router.post("/webhook/negative-event", include_in_schema=False)
async def negative_event_callback(
    background_tasks: BackgroundTasks,
    callback_data: Dict[str, Any] = Body(...),
    db: Session = Depends(database.get_db)
):
    """
    Webhook endpoint to receive callbacks from OpenAPI after a negative event check is complete.
    This endpoint is not exposed in the public API documentation.
    """
    try:
        # Extract the ID and status from the callback data
        external_id = callback_data.get('id')
        status = callback_data.get('status')
        
        if not external_id:
            raise HTTPException(status_code=400, detail="Missing ID in callback data")
        
        # Find the corresponding request in the database
        db_request = db.query(models.NegativaRequest).filter(
            models.NegativaRequest.external_id == external_id
        ).first()
        
        if not db_request:
            raise HTTPException(status_code=404, detail=f"Request with external ID {external_id} not found")
        
        # Update the request with callback data
        db_request.callback_json = callback_data
        db_request.status = status or "CALLBACK_RECEIVED"
        db.add(db_request)
        db.commit()
        
        # If the status is "COMPLETED", fetch the detail in the background
        if status == "COMPLETED":
            background_tasks.add_task(
                fetch_negative_detail, 
                request_id=db_request.id,
                external_id=external_id,
                db=db
            )
        
        # Return success
        return {"message": "Callback received successfully", "request_id": db_request.id}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing callback: {str(e)}")

# Custom function to modify OpenAPI schema generation
def custom_openapi(app):
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="BFlows OpenAPI Proxy",
        version="1.0.0",
        description="FastAPI proxy service for OpenAPI with versioning support",
        routes=app.routes,
    )
    
    # The webhook route is already excluded via include_in_schema=False
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema
