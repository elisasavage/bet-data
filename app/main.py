"""
Bet Data Panel - FastAPI uygulaması (Coolify / self-hosted).

Railway/Vercel versiyonundan farkı: normal sunucu ortamı, bağlantı havuzu açık.
"""

import mimetypes
import time
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, HTTPException, status, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from fastapi.middleware.gzip import GZipMiddleware

from app import stats_cache
from app.config import get_settings
from app.database import engine, Base
from app.routers import kisiler, search, tcsizler
from app.auth import login_with_supabase, get_current_user, get_optional_user
from app.schemas import LoginRequest

settings = get_settings()
BASE_PATH = Path(__file__).resolve().parent.parent

_login_attempts: dict = {}
_login_lock = threading.Lock()


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def check_login_rate_limit(request: Request) -> None:
    ip = _client_ip(request)
    now = time.time()
    window = settings.login_window_seconds
    with _login_lock:
        attempts = [t for t in _login_attempts.get(ip, []) if now - t < window]
        if len(attempts) >= settings.login_max_attempts:
            retry = int(window - (now - attempts[0]))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Çok fazla giriş denemesi. Lütfen biraz sonra tekrar deneyin.",
                headers={"Retry-After": str(max(retry, 1))},
            )
        attempts.append(now)
        _login_attempts[ip] = attempts


def _set_auth_cookies(response, access_token: str, refresh_token: str) -> None:
    common = {"httponly": True, "secure": settings.cookie_secure, "samesite": "strict"}
    response.set_cookie("access_token", access_token, max_age=3600, **common)
    response.set_cookie("refresh_token", refresh_token, max_age=86400 * 7, **common)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Veritabani hazir olmasa bile uygulama ayaga kalksin; /health her zaman cevap verir.
    # Tablolar zaten restore ile olusturuldu; create_all yalnizca emniyet kemeri.
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as exc:  # noqa: BLE001
        print("UYARI: veritabani semasi dogrulanamadi: %s" % exc)
    # Istatistikleri arka planda hazirla; ilk kullanici beklemesin.
    stats_cache.warm_in_background()
    yield


app = FastAPI(
    title=settings.app_name,
    description="Bet Data Yönetim Paneli",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Arama sonuclari (100-500 satir JSON) sikistirilarak gonderilir.
app.add_middleware(GZipMiddleware, minimum_size=1024)

# python:3.11-slim .webp'i tanimiyor; ikonlar application/octet-stream gitmesin.
mimetypes.add_type("image/webp", ".webp")


class _StaticFiles(StaticFiles):
    """3D ikonlar degismez; tarayici her sayfada yeniden sormasin (CSS yine ETag ile dogrulanir)."""

    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        if response.status_code == 200 and path.replace("\\", "/").startswith("icons/"):
            response.headers["Cache-Control"] = "public, max-age=2592000, immutable"
        return response


app.mount("/static", _StaticFiles(directory=str(BASE_PATH / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_PATH / "templates"))

app.include_router(kisiler.router)
app.include_router(search.router)
app.include_router(tcsizler.router)


@app.post("/api/auth/login")
async def api_login(request: Request, login_data: LoginRequest):
    check_login_rate_limit(request)
    return await login_with_supabase(login_data.email, login_data.password)


@app.post("/auth/login")
async def form_login(request: Request, email: str = Form(...), password: str = Form(...)):
    try:
        check_login_rate_limit(request)
        result = await login_with_supabase(email, password)
        response = RedirectResponse(url="/dashboard", status_code=303)
        _set_auth_cookies(response, result["access_token"], result["refresh_token"])
        return response
    except HTTPException as exc:
        message = exc.detail if exc.status_code == status.HTTP_429_TOO_MANY_REQUESTS else "Email veya şifre hatalı"
        return templates.TemplateResponse(
            request, "login.html", {"error": message}, status_code=exc.status_code
        )


@app.get("/auth/logout")
async def logout():
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return response


@app.get("/", response_class=HTMLResponse)
async def login_page(request: Request):
    if await get_optional_user(request):
        return RedirectResponse(url="/dashboard", status_code=303)
    return templates.TemplateResponse(request, "login.html")


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    if not await get_optional_user(request):
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(request, "dashboard.html")


@app.get("/arama", response_class=HTMLResponse)
async def search_page(request: Request):
    if not await get_optional_user(request):
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(request, "search.html")


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/health/db")
async def health_db():
    """Veritabani baglantisini ayrica dogrular."""
    from sqlalchemy import text
    from app.database import engine as _engine
    try:
        with _engine.connect() as conn:
            one = conn.execute(text("select 1")).scalar()
            tables = conn.execute(text(
                "select count(*) from information_schema.tables where table_schema='public'"
            )).scalar()
        return {"db": "ok", "select": one, "public_tables": tables}
    except Exception as exc:  # noqa: BLE001
        return {"db": "error", "detail": str(exc)[:200]}
