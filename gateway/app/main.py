"""
Golden Codex API Gateway

AI-powered image enrichment and provenance tracking.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

from . import __version__
from .config import get_settings
from .routers import account, estimate, jobs


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    settings = get_settings()
    print(f"Starting Golden Codex API Gateway v{__version__}")
    print(f"Environment: {settings.environment}")
    print(f"GCP Project: {settings.gcp_project}")
    yield
    # Shutdown
    print("Shutting down Golden Codex API Gateway")


app = FastAPI(
    title="Golden Codex API",
    description="""
AI-powered image enrichment and provenance tracking.

## Features

- **Nova** - AI metadata generation (50+ fields)
- **Flux** - 4K ESRGAN upscaling
- **Atlas** - Metadata infusion into image files

## Authentication

All endpoints require an API key in the Authorization header:

```
Authorization: Bearer gcx_live_your_key_here
```

Get your API key at [golden-codex.com/dashboard](https://golden-codex.com/dashboard)

## Rate Limits

| Tier | Requests/min |
|------|--------------|
| Free | 10 |
| Curator | 30 |
| Studio | 100 |
| Gallery | 300 |

## Support

- Email: api@golden-codex.com
- Docs: [golden-codex.com/docs/api](https://golden-codex.com/docs/api)
""",
    version=__version__,
    docs_url=None,  # We'll customize these
    redoc_url=None,
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Custom OpenAPI schema
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="Golden Codex API",
        version=__version__,
        description=app.description,
        routes=app.routes,
    )

    # Add security scheme
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "API Key",
            "description": "Use your API key: Bearer gcx_live_xxx",
        }
    }

    # Apply security globally
    openapi_schema["security"] = [{"BearerAuth": []}]

    # Add servers
    openapi_schema["servers"] = [
        {"url": "https://api.golden-codex.com/v1", "description": "Production"},
        {"url": "https://api-sandbox.golden-codex.com/v1", "description": "Sandbox"},
    ]

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


# Documentation endpoints
@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui():
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title="Golden Codex API - Docs",
        swagger_favicon_url="https://golden-codex.com/favicon.ico",
    )


@app.get("/redoc", include_in_schema=False)
async def custom_redoc():
    return get_redoc_html(
        openapi_url="/openapi.json",
        title="Golden Codex API - Reference",
        redoc_favicon_url="https://golden-codex.com/favicon.ico",
    )


# Health check (no auth required)
@app.get(
    "/health",
    tags=["Utilities"],
    summary="Health check",
    description="Check if the API is operational.",
)
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": __version__,
    }


# Include routers
app.include_router(jobs.router, prefix="/v1")
app.include_router(account.router, prefix="/v1")
app.include_router(estimate.router, prefix="/v1")


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle uncaught exceptions."""
    settings = get_settings()

    # Log the error (in production, use proper logging)
    print(f"Unhandled exception: {exc}")

    if settings.debug:
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": str(exc),
                }
            },
        )

    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "internal_error",
                "message": "An unexpected error occurred",
            }
        },
    )


# Root redirect
@app.get("/", include_in_schema=False)
async def root():
    """Redirect to docs."""
    return {"message": "Golden Codex API", "docs": "/docs", "version": __version__}
