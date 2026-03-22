import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.config import get_settings
from app.core.database import init_db
from app.services.price_fetcher import start_price_refresh_loop
from app.api.auth import router as auth_router
from app.api.models_api import router as models_router
from app.api.estimate import router as estimate_router
from app.api.deploy import router as deploy_router
from app.api.chat import router as chat_router
from app.api.pricing import router as pricing_router
from app.api.subscription import router as subscription_router
from app.api.builder import router as builder_router
from app.api.credentials import router as credentials_router
from app.api.managed import router as managed_router
from app.api.analytics import router as analytics_router
from app.api.playground import router as playground_router
from app.api.alerts import router as alerts_router
from app.api.compare import router as compare_router
from app.api.share import router as share_router
from app.api.recommend import router as recommend_router
from app.api.agent import router as agent_router
from app.api.workflow import router as workflow_router
from app.api.infra import router as infra_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    task = asyncio.create_task(start_price_refresh_loop())
    yield
    task.cancel()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if not settings.DEBUG:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


app.add_middleware(SecurityHeadersMiddleware)

cors_origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Webhook-Secret", "X-Callback-Secret"],
)

# ── Routes ──
app.include_router(auth_router, prefix="/api")
app.include_router(models_router, prefix="/api")
app.include_router(estimate_router, prefix="/api")
app.include_router(deploy_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(pricing_router, prefix="/api")
app.include_router(subscription_router, prefix="/api")
app.include_router(builder_router, prefix="/api")
app.include_router(credentials_router, prefix="/api")
app.include_router(managed_router, prefix="/api")
app.include_router(analytics_router, prefix="/api")
app.include_router(playground_router, prefix="/api")
app.include_router(alerts_router, prefix="/api")
app.include_router(compare_router, prefix="/api")
app.include_router(share_router, prefix="/api")
app.include_router(recommend_router, prefix="/api")
app.include_router(agent_router, prefix="/api")
app.include_router(workflow_router, prefix="/api")
app.include_router(infra_router, prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": settings.APP_VERSION}
