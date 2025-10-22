from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, Union
from datetime import datetime

# Credit Score Schemas
class CreditScoreResponse(BaseModel):
    id: int
    identifier: str
    response_json: Dict[str, Any]
    status_code: int
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Negative Events Schemas
class CallbackConfig(BaseModel):
    url: str
    method: str
    field: str
    headers: Optional[Dict[str, str]] = None

class NegativaCreateRequest(BaseModel):
    cf_piva: str
    callback: CallbackConfig

class NegativaCallbackData(BaseModel):
    id: str
    status: str
    esito: Optional[Dict[str, Any]] = None
    data: Optional[Dict[str, Any]] = None
    
    class Config:
        extra = "allow"  # Allow extra fields to be flexible with callback data

class NegativaInitialResponse(BaseModel):
    id: int
    external_id: str
    cf_piva: str
    status: str
    request_json: Dict[str, Any]
    response_json: Dict[str, Any]
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class NegativaDetailResponse(BaseModel):
    id: int
    request_id: int
    detail_json: Dict[str, Any]
    presence_pregiudizievoli: bool
    presence_procedure: bool
    presence_protesti: bool
    status_code: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class NegativaFullResponse(BaseModel):
    request: NegativaInitialResponse
    detail: Optional[NegativaDetailResponse] = None
    
    class Config:
        from_attributes = True
