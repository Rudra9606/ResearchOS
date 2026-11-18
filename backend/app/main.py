from fastapi import FastAPI, Request
from uuid import uuid4
from fastapi.responses import JSONResponse
from sqlalchemy import text
from app.db.session import engine
from app.api.v1.router import api_router
from app.core.config import settings
from app.utils.exceptions import ResearchOSException
from app.utils.logging import get_logger
from app.utils.request_context import request_id_context

logger = get_logger(__name__)

app = FastAPI(
    title="ResearchOS API",
    description="Backend API for the ResearchOS AI Research Platform",
    version="1.0.0",
)


@app.middleware("http")
async def correlate_request(request: Request, call_next):
    supplied = request.headers.get("x-request-id", "")
    request_id = supplied if len(supplied) <= 64 and supplied.isascii() and supplied.replace("-", "").replace("_", "").replace(".", "").isalnum() else str(uuid4())
    context_token = request_id_context.set(request_id)
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        request_id_context.reset(context_token)


@app.exception_handler(ResearchOSException)
async def research_os_exception_handler(request: Request, exc: ResearchOSException):
    logger.error(f"ResearchOSException: {exc.message}", extra={"details": exc.details})
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "message": exc.message,
            "details": exc.details,
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {type(exc).__name__}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "message": "An internal server error occurred.",
        },
    )


@app.get("/")
async def root():
    return {
        "message": "Welcome to ResearchOS API!",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "application": "ResearchOS"
    }


app.include_router(
    api_router,
    prefix="/api/v1"
)


@app.get("/api/v1/database/check")
def check_database():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            return {
                "status": "success",
                "message": "ResearchOS database connected."
            }
    except Exception as e:
        logger.error("Database health check failed", exc_info=True)
        return {
            "status": "error",
            "message": "Database is unavailable.",
        }
