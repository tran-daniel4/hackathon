import time
from typing import Any

import httpx
from jose import JWTError, jwk, jwt
from jose.utils import base64url_decode

from core.config import settings

_JWKS_CACHE_TTL_SECONDS = 300
_jwks_cache: dict[str, Any] = {"keys": None, "fetched_at": 0.0}


async def _get_jwks() -> list[dict[str, Any]]:
    if not settings.supabase_url:
        raise JWTError("SUPABASE_URL is not configured")

    now = time.time()
    cached_keys = _jwks_cache["keys"]
    fetched_at = _jwks_cache["fetched_at"]
    if cached_keys and (now - fetched_at) < _JWKS_CACHE_TTL_SECONDS:
        return cached_keys

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(f"{settings.supabase_url}/auth/v1/.well-known/jwks.json")
        response.raise_for_status()
        payload = response.json()

    keys = payload.get("keys", [])
    if not isinstance(keys, list) or not keys:
        raise JWTError("Supabase JWKS endpoint returned no signing keys")

    _jwks_cache["keys"] = keys
    _jwks_cache["fetched_at"] = now
    return keys


def _verify_signature(token: str, key_data: dict[str, Any], algorithm: str) -> None:
    message, encoded_signature = token.rsplit(".", 1)
    decoded_signature = base64url_decode(encoded_signature.encode())
    key = jwk.construct(key_data, algorithm)
    if not key.verify(message.encode(), decoded_signature):
        raise JWTError("Signature verification failed")


async def decode_token(token: str) -> dict[str, Any]:
    try:
        header = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise JWTError("Invalid token header") from exc

    kid = header.get("kid")
    alg = header.get("alg")
    if not kid or not alg:
        raise JWTError("Missing token signing metadata")

    keys = await _get_jwks()
    key_data = next((item for item in keys if item.get("kid") == kid), None)
    if key_data is None:
        raise JWTError("No matching signing key found")

    _verify_signature(token, key_data, alg)

    try:
        return jwt.get_unverified_claims(token)
    except JWTError as exc:
        raise JWTError("Invalid token claims") from exc


def validate_claims(claims: dict[str, Any]) -> dict[str, Any]:
    if not settings.supabase_url:
        raise JWTError("SUPABASE_URL is not configured")

    now = int(time.time())
    issuer = claims.get("iss")
    audience = claims.get("aud")
    subject = claims.get("sub")
    expires_at = claims.get("exp")
    role = claims.get("role")

    if issuer != f"{settings.supabase_url}/auth/v1":
        raise JWTError("Invalid issuer")

    if isinstance(audience, list):
        audience_valid = "authenticated" in audience
    else:
        audience_valid = audience == "authenticated"
    if not audience_valid:
        raise JWTError("Invalid audience")

    if role != "authenticated":
        raise JWTError("Invalid role")

    if not isinstance(subject, str) or not subject:
        raise JWTError("Missing subject")

    if not isinstance(expires_at, int) or expires_at <= now:
        raise JWTError("Token expired")

    return claims
