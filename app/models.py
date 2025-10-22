from sqlalchemy import Column, Integer, String, JSON, DateTime, func, text, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base
import os

# Get timezone from environment variables
TIMEZONE = os.getenv("TIMEZONE", "UTC")

# Custom function to get current time in the specified timezone
timezone_now = func.timezone(TIMEZONE, func.now())

class CreditScoreResponse(Base):
    __tablename__ = "credit_score_responses"

    id = Column(Integer, primary_key=True, index=True)
    identifier = Column(String, index=True, nullable=False)  # vatCode, taxCode, or company ID - removed unique constraint to allow multiple records with same identifier
    response_json = Column(JSON)
    status_code = Column(Integer)
    status = Column(String, default="ACTIVE", nullable=False)  # Can be "ACTIVE" or "NOT ACTIVE"
    created_at = Column(DateTime(timezone=True), server_default=timezone_now)
    updated_at = Column(DateTime(timezone=True), onupdate=timezone_now)

class CompanyFullData(Base):
    __tablename__ = "company_full_data"
    
    id = Column(Integer, primary_key=True, index=True)
    identifier = Column(String, index=True, nullable=False)  # VAT or tax code
    external_id = Column(String, index=True, nullable=True)  # ID from the OpenAPI service
    status = Column(String, default="PENDING", nullable=False)  # PENDING, COMPLETED, ERROR
    version_status = Column(String, default="ACTIVE", nullable=False)  # Can be "ACTIVE" or "NOT ACTIVE" for versioning
    request_json = Column(JSON)  # Original request data
    response_json = Column(JSON)  # Response from initial request
    callback_json = Column(JSON, nullable=True)  # Complete callback data (including detailed information)
    status_code = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=timezone_now)
    updated_at = Column(DateTime(timezone=True), onupdate=timezone_now)

class NegativaRequest(Base):
    __tablename__ = "negativa_requests"
    
    id = Column(Integer, primary_key=True, index=True)
    external_id = Column(String, index=True, nullable=False)  # ID from the OpenAPI service
    cf_piva = Column(String, index=True, nullable=False)  # Tax code or VAT number
    status = Column(String, nullable=False, default="PENDING")  # PENDING, COMPLETED, ERROR
    version_status = Column(String, default="ACTIVE", nullable=False)  # Can be "ACTIVE" or "NOT ACTIVE" for versioning
    request_json = Column(JSON)  # Original request data
    response_json = Column(JSON)  # Response from initial request
    callback_json = Column(JSON, nullable=True)  # Data received from callback
    created_at = Column(DateTime(timezone=True), server_default=timezone_now)
    updated_at = Column(DateTime(timezone=True), onupdate=timezone_now)
    
    # Relationship with the details
    detail = relationship("NegativaDetail", back_populates="request", uselist=False)

class NegativaDetail(Base):
    __tablename__ = "negativa_details"
    
    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("negativa_requests.id"))
    detail_json = Column(JSON)  # Detailed data from the second API call
    presence_pregiudizievoli = Column(Boolean, default=False)
    presence_procedure = Column(Boolean, default=False)
    presence_protesti = Column(Boolean, default=False)
    status_code = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=timezone_now)
    updated_at = Column(DateTime(timezone=True), onupdate=timezone_now)
    
    # Relationship with the request
    request = relationship("NegativaRequest", back_populates="detail")
