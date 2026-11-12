"""
Supabase Auth dogrulama (yerel JWT + opsiyonel uzak dogrulama).

Avantaj: token dogrulamasi icin her istekte Supabase'e HTTP cagrisi yapilmaz;
JWT imzasi paylasilan sir ile yerel olarak cozulur. Bu, panelin ag
gecikmelerinden ve Supabase erisilemezliginden bagimsiz calismasini saglar.
"""

import httpx
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.config import get_settings

settings = get_settings()
security = HTTPBearer(auto_error=False)

ALGORITHM = "HS256"


def _decode_local(token: str) -> dict | None:
    """JWT'yi paylasilan secret ile yerel olarak dogrula."""
    if not token or not settings.supabase_jwt_secret:
        return None
    try:
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=[ALGORITHM],
            options={"verify_aud": False},
        )
    except JWTError:
        return None
    sub = payload.get("sub")
    if not sub:
        return None
    return {
        "sub": sub,
        "email": payload.get("email"),
        "role": payload.get("role"),
        "user": payload,
    }


async def _fetch_user_remote(token: str) -> dict | None:
    """Yedek yol: token'i Supabase /auth/v1/user ile dogrula."""
    for base in settings.supabase_base_urls:
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                response = await client.get(
                    f"{base}/auth/v1/user",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "apikey": settings.supabase_key,
                    },
                )
            if response.status_code != 200:
                continue
            data = response.json()
            return {
                "sub": data.get("id"),
                "email": data.get("email"),
                "role": data.get("role"),
                "user": data,
            }
        except httpx.RequestError:
            continue
    return None


async def _verify_token(token: str) -> dict | None:
    """Once yerel JWT, olmazsa uzak dogrulama."""
    user = _decode_local(token)
    if user:
        return user
    return await _fetch_user_remote(token)


def _extract_token(request: Request, credentials: HTTPAuthorizationCredentials | None) -> str | None:
    """Once Authorization header, yoksa httponly access_token cookie'si."""
    if credentials and credentials.credentials:
        return credentials.credentials
    return request.cookies.get("access_token")


async def verify_supabase_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """API uclari icin token dogrulama."""
    token = _extract_token(request, credentials)
    user = await _verify_token(token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token doğrulanamadı",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_optional_user(request: Request) -> dict | None:
    """Sayfa route'lari icin: cookie token'ini dogrula, gecersizse None."""
    return await _verify_token(request.cookies.get("access_token"))


async def get_current_user(
    request: Request,
    token_payload: dict = Depends(verify_supabase_token),
) -> dict:
    """Mevcut kullaniciyi dondur."""
    user_id = token_payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz token",
        )
    return {"id": user_id, "email": token_payload.get("email")}


async def login_with_supabase(email: str, password: str) -> dict:
    """Supabase Auth ile sifre girisi."""
    last_error = None
    for base in settings.supabase_base_urls:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    f"{base}/auth/v1/token?grant_type=password",
                    json={"email": email, "password": password},
                    headers={
                        "apikey": settings.supabase_key,
                        "Content-Type": "application/json",
                    },
                )
            if response.status_code == 200:
                return response.json()
            last_error = response.status_code
        except httpx.RequestError as exc:
            last_error = exc

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Email veya şifre hatalı (%s)" % last_error,
    )


async def refresh_token(refresh_token_value: str) -> dict:
    """Token yenile."""
    for base in settings.supabase_base_urls:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    f"{base}/auth/v1/token?grant_type=refresh_token",
                    json={"refresh_token": refresh_token_value},
                    headers={
                        "apikey": settings.supabase_key,
                        "Content-Type": "application/json",
                    },
                )
            if response.status_code == 200:
                return response.json()
        except httpx.RequestError:
            continue

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token yenilenemedi",
    )
