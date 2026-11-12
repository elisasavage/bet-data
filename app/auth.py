"""
Supabase Auth JWT verification middleware
"""

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
import httpx
from app.config import get_settings

settings = get_settings()
# auto_error=False: header yoksa 403 fırlatma; cookie'ye geri düşebilelim
security = HTTPBearer(auto_error=False)


async def _fetch_user(token: str) -> dict | None:
    """Token'ı Supabase ile doğrula. Geçerliyse kullanıcı dict'i, değilse None."""
    if not token:
        return None
    # Once ic ag (hizli), olmazsa public URL (yedek) denenir.
    for base in settings.supabase_base_urls:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{base}/auth/v1/user",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "apikey": settings.supabase_key
                    }
                )
            if response.status_code != 200:
                continue
            user_data = response.json()
            return {
                "sub": user_data.get("id"),
                "email": user_data.get("email"),
                "user": user_data
            }
        except httpx.RequestError:
            continue
    return None


def _extract_token(request: Request, credentials: HTTPAuthorizationCredentials | None) -> str | None:
    """Önce Authorization header, yoksa httponly access_token cookie'si."""
    if credentials and credentials.credentials:
        return credentials.credentials
    return request.cookies.get("access_token")


async def verify_supabase_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    Supabase JWT token'ı doğrula (header veya cookie). API uçları için.
    """
    token = _extract_token(request, credentials)
    user = await _fetch_user(token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token doğrulanamadı",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return user


async def get_optional_user(request: Request) -> dict | None:
    """Sayfa route'ları için: cookie'deki token'ı doğrula, geçersizse None döndür (yönlendirme çağıran tarafta)."""
    return await _fetch_user(request.cookies.get("access_token"))


async def get_current_user(
    request: Request,
    token_payload: dict = Depends(verify_supabase_token)
) -> dict:
    """
    Mevcut kullanıcıyı al
    """
    user_id = token_payload.get("sub")
    email = token_payload.get("email")
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz token"
        )
    
    return {
        "id": user_id,
        "email": email
    }


async def login_with_supabase(email: str, password: str) -> dict:
    """
    Supabase ile giriş yap
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{settings.supabase_url}/auth/v1/token?grant_type=password",
            json={
                "email": email,
                "password": password
            },
            headers={
                "apikey": settings.supabase_key,
                "Content-Type": "application/json"
            }
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email veya şifre hatalı"
            )
        
        return response.json()


async def refresh_token(refresh_token: str) -> dict:
    """
    Token yenile
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{settings.supabase_url}/auth/v1/token?grant_type=refresh_token",
            json={
                "refresh_token": refresh_token
            },
            headers={
                "apikey": settings.supabase_key,
                "Content-Type": "application/json"
            }
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token yenilenemedi"
            )
        
        return response.json()
