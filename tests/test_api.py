import pytest
import httpx
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from main import app, get_db, Base

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
test_engine = create_async_engine(TEST_DATABASE_URL)
TestSessionLocal = sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest.fixture(autouse=True)
async def setup_database():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def override_get_db():
    async with TestSessionLocal() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest.mark.asyncio
async def test_create_deadline():
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/deadlines",
            json={
                "user_id": 1,
                "title": "Test Deadline",
                "end_date": "2026-12-31",
                "priority": 1,
                "category": "test",
            },
        )

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test Deadline"
    assert data["id"] is not None
    assert data["is_completed"] is False


@pytest.mark.asyncio
async def test_get_deadlines_not_found():
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/deadlines/999")

    assert response.status_code == 404
    assert response.json()["detail"] == "No deadlines found for this user"
