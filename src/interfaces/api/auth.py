"""
Telegram WebApp authentication.

Validates initData from Telegram Mini App using HMAC-SHA256.
Reference: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""

import hashlib
import hmac
import json
import urllib.parse
from dataclasses import dataclass

from fastapi import HTTPException, Request, status

from src.config import config


@dataclass
class TelegramUser:
    """Validated Telegram user from initData."""

    id: int
    first_name: str
    last_name: str | None = None
    username: str | None = None
    language_code: str | None = None
    is_premium: bool = False
    photo_url: str | None = None


def validate_init_data(init_data: str, bot_token: str) -> dict | None:
    """
    Validate Telegram WebApp initData.

    Args:
        init_data: Raw initData string from Telegram WebApp
        bot_token: Bot token for HMAC verification

    Returns:
        Parsed data dict if valid, None otherwise
    """
    if not init_data:
        return None

    # Parse URL-encoded data
    try:
        parsed = urllib.parse.parse_qs(init_data, keep_blank_values=True)
        # parse_qs returns lists, flatten to single values
        data = {k: v[0] if len(v) == 1 else v for k, v in parsed.items()}
    except Exception:
        return None

    # Extract hash
    received_hash = data.pop("hash", None)
    if not received_hash:
        return None

    # Build data-check-string (sorted key=value pairs joined by \n)
    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(data.items()) if v is not None
    )

    # Generate secret key: HMAC-SHA256(bot_token, "WebAppData")
    secret_key = hmac.new(
        b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256
    ).digest()

    # Calculate expected hash
    expected_hash = hmac.new(
        secret_key, data_check_string.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    # Constant-time comparison
    if not hmac.compare_digest(expected_hash, received_hash):
        return None

    return data


def parse_telegram_user(data: dict) -> TelegramUser | None:
    """
    Parse user object from validated initData.

    Args:
        data: Validated initData dict

    Returns:
        TelegramUser if user data exists, None otherwise
    """
    user_json = data.get("user")
    if not user_json:
        return None

    try:
        user_data = json.loads(user_json)
        return TelegramUser(
            id=user_data["id"],
            first_name=user_data.get("first_name", ""),
            last_name=user_data.get("last_name"),
            username=user_data.get("username"),
            language_code=user_data.get("language_code"),
            is_premium=user_data.get("is_premium", False),
            photo_url=user_data.get("photo_url"),
        )
    except (json.JSONDecodeError, KeyError):
        return None


async def get_current_user(request: Request) -> TelegramUser:
    """
    FastAPI dependency for authenticated endpoints.

    Extracts and validates Telegram user from Authorization header.

    Usage:
        @router.get("/api/me")
        async def get_me(user: TelegramUser = Depends(get_current_user)):
            ...

    Raises:
        HTTPException 401 if auth fails
    """
    auth_header = request.headers.get("Authorization")

    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing",
        )

    # Expect format: "tma <initData>"
    parts = auth_header.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "tma":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization format. Expected: tma <initData>",
        )

    init_data = parts[1]

    # Validate initData
    validated_data = validate_init_data(init_data, config.BOT_TOKEN.get_secret_value())
    if not validated_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid initData signature",
        )

    # Parse user
    user = parse_telegram_user(validated_data)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User data not found in initData",
        )

    return user
