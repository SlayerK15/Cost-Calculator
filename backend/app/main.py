import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://127.0.0.1:3000", "http://127.0.0.1:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": settings.APP_VERSION}
