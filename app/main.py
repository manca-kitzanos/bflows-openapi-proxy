from fastapi import FastAPI
from . import models, database, routes

models.Base.metadata.create_all(bind=database.engine)

# Configure FastAPI with detailed metadata for Swagger UI
app = FastAPI(
    title="Bflows OpenAPI Proxy",
    description="""
    API for proxying requests to OpenAPI service.
    
    This service provides a proxy to access data from an external OpenAPI service.
    Responses are stored in a database for caching and version tracking.
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Apply custom OpenAPI schema to hide webhook endpoints
app.openapi = lambda: routes.custom_openapi(app)

# Include router from the routes file
app.include_router(routes.router)
