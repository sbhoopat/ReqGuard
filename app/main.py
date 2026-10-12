"""Main FastAPI application entry point for ReqGuard AI."""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.api.webhooks import router as webhooks_router
from app.api.analysis import router as analysis_router

# Configure logging
logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s"
)
logger = logging.getLogger("reqguard")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("ReqGuard AI server starting up...")
    logger.info(f"Environment: {settings.APP_ENV} | Groq Model: {settings.GROQ_MODEL}")
    yield
    logger.info("ReqGuard AI server shutting down...")


app = FastAPI(
    title="ReqGuard AI — Requirement Compliance Checker",
    description="AI-powered GitHub Pull Request compliance checker against Jira Cloud acceptance criteria.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(webhooks_router)
app.include_router(analysis_router)


@app.get("/health", tags=["system"])
async def health_check():
    """Health check endpoint returning service status and active configurations."""
    return {
        "status": "healthy",
        "service": "ReqGuard AI",
        "version": "1.0.0",
        "environment": settings.APP_ENV,
        "groq_model": settings.GROQ_MODEL,
        "jira_base_configured": bool(settings.JIRA_BASE_URL),
        "github_configured": bool(settings.GITHUB_TOKEN),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
