import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import text

from app.main import app
from app.core.database import get_db
from app.core.config import settings

@pytest.fixture(scope="session")
async def test_engine():
    """Create a session-scoped async engine."""
    engine = create_async_engine(
        settings.test_database_url,
        echo=False,
    )
    yield engine
    await engine.dispose()

@pytest.fixture
async def db_session(test_engine):
    """
    Async database session fixture for testing.
    Resets the database before each test and provides a clean session.
    """
    async with test_engine.begin() as conn:
        # Clear all tables using the function provided by db-schema-engineer
        await conn.execute(text("SELECT truncate_all_tables_test();"))
    
    SessionLocal = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with SessionLocal() as session:
        yield session

@pytest.fixture
async def client(db_session):
    """
    Test client fixture providing httpx.AsyncClient.
    Overrides the get_db dependency to use the testing session.
    """
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(
        transport=ASGITransport(app=app), 
        base_url="http://test"
    ) as ac:
        yield ac
    
    app.dependency_overrides.clear()
