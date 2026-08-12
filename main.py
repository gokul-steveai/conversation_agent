import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.v1.auth import router as auth_router
from api.v1.chat import router as chat_router
from api.v1.sessions import router as session_router
from config.settings import settings
from core.database import DatabaseManager
from utils.logger import logger

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await DatabaseManager.init_engine()
    yield
    await DatabaseManager.close_engine()


app = FastAPI(
    title="AI Chat Assistant API",
    description="Production-Grade FastAPI Backend for AI Agent Chat, JWT Authentication, and Persistent Session Management",
    version="1.0.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def request_tracing_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id

    start_time = time.perf_counter()
    response = await call_next(request)
    process_time = time.perf_counter() - start_time

    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = f"{process_time:.4f}s"
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    request_id = getattr(request.state, "request_id", "unknown")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail,
            "status_code": exc.status_code,
            "request_id": request_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", "unknown")
    logger.error(
        f"Unhandled exception [Request-ID: {request_id}]: {exc}", exc_info=True
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": "An internal server error occurred.",
            "status_code": 500,
            "request_id": request_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(session_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {
        "status": "online",
        "title": "AI Chat Assistant API",
        "environment": settings.environment,
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    db_status = "connected" if DatabaseManager._engine is not None else "initializing"
    return {
        "status": "healthy",
        "database": db_status,
        "environment": settings.environment,
        "llm_model": settings.groq_model,
        "search_tool": "Tavily" if settings.tavily_api_key else "Fallback",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
