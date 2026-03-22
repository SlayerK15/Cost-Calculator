"""
Shared fixtures for the CostCalculator backend test suite.

Provides:
- Async in-memory SQLite engine + tables
- AsyncSession factory
- httpx.AsyncClient wired to a lifespan-free FastAPI app
- Helper functions to register/login users at each tier
"""

import os

# Ensure tests run in debug mode so insecure default secrets are allowed
os.environ.setdefault("DEBUG", "true")

import asyncio
import pytest
import pytest_asyncio
from contextlib import asynccontextmanager
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.core.database import Base, get_db
from app.core.security import hash_password, create_access_token
from app.models.models import User, UserTier

# ---------------------------------------------------------------------------
# Engine & session scoped to the test session
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
_TestSession = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop():
    """Single event loop for the whole test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _create_tables():
    """Create all DB tables once at the start of the test session."""
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    """Per-test database session with automatic rollback."""
    async with _TestSession() as session:
        yield session
        await session.rollback()


# ---------------------------------------------------------------------------
# FastAPI test client — uses a no-op lifespan to avoid price_fetcher loop
# ---------------------------------------------------------------------------

def _build_test_app():
    """Build a copy of the FastAPI app with an empty lifespan (no bg tasks)."""
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from app.core.config import get_settings

    # Import all routers just like main.py
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
    async def _noop_lifespan(app):
        yield  # no init_db, no price_refresh_loop

    test_app = FastAPI(title="Test", lifespan=_noop_lifespan)
    test_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"], allow_credentials=True,
        allow_methods=["*"], allow_headers=["*"],
    )

    for r in [
        auth_router, models_router, estimate_router, deploy_router,
        chat_router, pricing_router, subscription_router, builder_router,
        credentials_router, managed_router, analytics_router, playground_router,
        alerts_router, compare_router, share_router, recommend_router, agent_router, workflow_router, infra_router,
    ]:
        test_app.include_router(r, prefix="/api")

    @test_app.get("/api/health")
    async def health():
        return {"status": "ok", "version": settings.APP_VERSION}

    return test_app


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncClient:
    """httpx AsyncClient that talks to a test FastAPI app with no bg tasks."""
    test_app = _build_test_app()

    async def _override_get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    test_app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

async def create_user(
    db: AsyncSession,
    email: str = "test@example.com",
    password: str = "testpass123",
    tier: UserTier = UserTier.FREE,
    full_name: str = "Test User",
) -> tuple[User, str]:
    """Create a user and return (user, jwt_token)."""
    user = User(
        email=email,
        hashed_password=hash_password(password),
        full_name=full_name,
        tier=tier,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    token = create_access_token({"sub": user.id, "email": user.email})
    return user, token


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _unique_email(prefix: str) -> str:
    import uuid
    return f"{prefix}-{uuid.uuid4().hex[:8]}@test.com"


@pytest_asyncio.fixture
async def free_user(db_session: AsyncSession):
    """Returns (user, token) for a FREE tier user."""
    return await create_user(db_session, email=_unique_email("free"), tier=UserTier.FREE)


@pytest_asyncio.fixture
async def pro_user(db_session: AsyncSession):
    """Returns (user, token) for a PRO tier user."""
    return await create_user(db_session, email=_unique_email("pro"), tier=UserTier.PRO)


@pytest_asyncio.fixture
async def enterprise_user(db_session: AsyncSession):
    """Returns (user, token) for an ENTERPRISE tier user."""
    return await create_user(db_session, email=_unique_email("enterprise"), tier=UserTier.ENTERPRISE)
