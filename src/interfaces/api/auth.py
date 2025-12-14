"""Telegram WebApp authentication validation.

Implements signature verification for Telegram Mini App initData.
Based on: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""

import hashlib
import hmac
import json
from typing import Optional
from urllib.parse import parse_qs, unquote

from fastapi import Header, HTTPException

from src.config import settings
from src.database.models import User


def verify_telegram_auth(init_data: str) -> dict:
    """Verify Telegram WebApp initData signature.

    Args:
        init_data: Raw initData string from Telegram.WebApp.initData

    Returns:
        dict: Parsed parameters from initData

    Raises:
        HTTPException: If signature is invalid or hash is missing
    """
    # Parse initData (URL-encoded query string)
    try:
        params = {}
        for key, value in parse_qs(init_data).items():
            params[key] = unquote(value[0]) if value else ""
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid initData format: {e}")

    # Extract hash
    hash_value = params.pop("hash", None)
    if not hash_value:
        raise HTTPException(status_code=401, detail="Missing hash in initData")

    # Create data-check-string
    data_check_string = "\n".join(
        f"{key}={value}" for key, value in sorted(params.items())
    )

    # Calculate secret key: HMAC-SHA256(bot_token, "WebAppData")
    secret_key = hmac.new(
        key=b"WebAppData",
        msg=settings.BOT_TOKEN.encode(),
        digestmod=hashlib.sha256,
    ).digest()

    # Calculate hash: HMAC-SHA256(secret_key, data-check-string)
    calculated_hash = hmac.new(
        key=secret_key,
        msg=data_check_string.encode(),
        digestmod=hashlib.sha256,
    ).hexdigest()

    # Verify hash
    if calculated_hash != hash_value:
        raise HTTPException(status_code=401, detail="Invalid hash signature")

    return params


async def get_current_user(
    x_telegram_init_data: Optional[str] = Header(None, alias="X-Telegram-Init-Data")
) -> User:
    """FastAPI dependency to get current user from Telegram auth.

    Args:
        x_telegram_init_data: Telegram initData from request header

    Returns:
        User: Authenticated user instance

    Raises:
        HTTPException: If auth fails or user not found
    """
    if not x_telegram_init_data:
        raise HTTPException(
            status_code=401,
            detail="Missing X-Telegram-Init-Data header",
        )

    # Verify signature
    params = verify_telegram_auth(x_telegram_init_data)

    # Extract user data
    user_json = params.get("user")
    if not user_json:
        raise HTTPException(status_code=401, detail="Missing user in initData")

    try:
        user_data = json.loads(user_json)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid user JSON: {e}")

    # Get user from database
    telegram_id = user_data.get("id")
    if not telegram_id:
        raise HTTPException(status_code=400, detail="Missing user ID")

    user = await User.filter(telegram_id=telegram_id).first()
    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found. Please start the bot first via /start",
        )

    return user
