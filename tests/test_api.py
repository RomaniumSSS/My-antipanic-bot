"""API endpoint tests.

To run:
    pytest tests/test_api.py -v

Note: These tests require a database with at least one user.
You can create a test user by running the bot and using /start.
"""

import pytest
from fastapi.testclient import TestClient

from src.database.models import User
from src.interfaces.api.main import app

client = TestClient(app)


def test_health_endpoint():
    """Test health check endpoint (no auth required)."""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_root_endpoint():
    """Test root endpoint (no auth required)."""
    response = client.get("/")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "Antipanic API"


def test_api_me_without_auth():
    """Test /api/me returns 401 without authentication."""
    response = client.get("/api/me")

    assert response.status_code == 401


def test_dev_list_users():
    """Test /dev/users endpoint lists users."""
    response = client.get("/dev/users")

    assert response.status_code == 200
    users = response.json()
    assert isinstance(users, list)


@pytest.mark.asyncio
async def test_dev_get_me():
    """Test /dev/me endpoint with valid telegram_id."""
    # Get first user from database
    user = await User.first()

    if not user:
        pytest.skip("No users in database. Run the bot with /start first.")

    response = client.get(f"/dev/me?telegram_id={user.telegram_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["telegram_id"] == user.telegram_id
    assert "xp" in data
    assert "level" in data
    assert "streak_days" in data


def test_dev_get_me_invalid_user():
    """Test /dev/me returns 404 for non-existent user."""
    response = client.get("/dev/me?telegram_id=999999999")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_dev_get_goals():
    """Test /dev/goals endpoint."""
    user = await User.first()

    if not user:
        pytest.skip("No users in database")

    response = client.get(f"/dev/goals?telegram_id={user.telegram_id}")

    # May return 404 if no active goal, which is fine
    assert response.status_code in [200, 404]

    if response.status_code == 200:
        data = response.json()
        assert "id" in data
        assert "title" in data


@pytest.mark.asyncio
async def test_dev_get_stats():
    """Test /dev/stats endpoint."""
    user = await User.first()

    if not user:
        pytest.skip("No users in database")

    response = client.get(f"/dev/stats?telegram_id={user.telegram_id}")

    assert response.status_code == 200
    data = response.json()
    assert "today" in data
    assert "week" in data
    assert "steps_assigned" in data["today"]
    assert "steps_completed" in data["today"]
    assert "active_days" in data["week"]


@pytest.mark.asyncio
async def test_dev_get_history():
    """Test /dev/history endpoint."""
    user = await User.first()

    if not user:
        pytest.skip("No users in database")

    response = client.get(f"/dev/history?telegram_id={user.telegram_id}")

    assert response.status_code == 200
    data = response.json()
    assert "steps" in data
    assert isinstance(data["steps"], list)


@pytest.mark.asyncio
async def test_dev_generate_microhit():
    """Test /dev/microhit/generate endpoint."""
    user = await User.first()

    if not user:
        pytest.skip("No users in database")

    response = client.post(
        f"/dev/microhit/generate?telegram_id={user.telegram_id}"
        "&step_title=Начать работу&blocker_type=fear"
    )

    # May fail if no active goal
    if response.status_code == 404:
        pytest.skip("No active goal for user")

    assert response.status_code == 200
    data = response.json()
    assert "options" in data
    assert "step_id" in data
    assert len(data["options"]) > 0
    assert all("text" in opt for opt in data["options"])


def test_openapi_schema():
    """Test that OpenAPI schema is generated correctly."""
    response = client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    assert "openapi" in schema
    assert "info" in schema
    assert schema["info"]["title"] == "Antipanic API"
