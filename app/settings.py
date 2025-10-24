from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Database settings
DATABASE_URL = os.getenv("DATABASE_URL")

# OpenAPI settings
OPENAPI_BASE_URL_RISK = os.getenv("OPENAPI_BASE_URL_RISK")
OPENAPI_TOKEN_RISK = os.getenv("OPENAPI_TOKEN_RISK")
OPENAPI_BASE_URL_COMPANY = os.getenv("OPENAPI_BASE_URL_COMPANY")
OPENAPI_TOKEN_COMPANY = os.getenv("OPENAPI_TOKEN_COMPANY")

# General settings
TIMEZONE = os.getenv("TIMEZONE", "Europe/Rome")
DEBUG = os.getenv("DEBUG", "False").lower() == "true"

# Email settings
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True").lower() == "true"
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER)
DEFAULT_NOTIFICATION_EMAIL = os.getenv("DEFAULT_NOTIFICATION_EMAIL", "antonio.manca@bflows.net")
