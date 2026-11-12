"""
TC'siz kayıtlar için router
"""

from fastapi import APIRouter, Depends, Query, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, literal_column, or_, select
from typing import Optional
from pathlib import Path

from app.database import get_db
from app.models import Tcsiz
from app.auth import get_current_user, get_optional_user
from app.schemas import SearchResponse, KisiListResponse
from app.stats_cache import tcsiz_stats

router = APIRouter(prefix="/tcsizler", tags=["TC'sizler"])

BASE_PATH = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=str(BASE_PATH / "templates"))

# idx_tcsizler_adsoyad_trgm index ifadesiyle ayni (concat(isim,' ',soyisim) esdegeri).
AD_SOYAD = literal_column("(coalesce(tcsizler.isim,'') || ' ' || coalesce(tcsizler.soyisim,''))")


@router.get("", response_class=HTMLResponse)
async def tcsizler_page(request: Request):
    """TC'sizler sayfası"""
    user = await get_optional_user(request)
    if not user:
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(request, "tcsizler.html")


@router.get("/api/list")
def get_tcsizler(
    q: Optional[str] = Query(None, description="İsim, soyisim veya telefon"),
    site: Optional[str] = Query(None, description="Site filtresi"),
    page: int = Query(1, ge=1),
    per_page: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    TC'siz kayıtları listele
    """
    filters = []

    # Text search
    if q:
        search_term = f"%{q}%"
        filters.append(or_(AD_SOYAD.ilike(search_term), Tcsiz.telefon.like(search_term)))

    # Site filtresi
    if site:
        filters.append(Tcsiz.site_adi == site)

    # Toplam sayı (filtresiz / yalniz-site: onbellekten)
    total = None
    if not q:
        stats = tcsiz_stats.get()
        total = stats["site_counts"].get(site) if site else stats["toplam"]
    if total is None:
        total = db.execute(select(func.count()).select_from(Tcsiz).where(*filters)).scalar() or 0

    # Pagination
    tcsizler = db.execute(
        select(Tcsiz.id, Tcsiz.isim, Tcsiz.soyisim, Tcsiz.telefon, Tcsiz.email, Tcsiz.site_adi)
        .where(*filters)
        .order_by(Tcsiz.created_at.desc(), Tcsiz.id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    ).all()

    items = [
        KisiListResponse(
            id=t.id,
            tc="",  # TC yok
            isim=t.isim,
            soyisim=t.soyisim,
            telefon_sayisi=1 if t.telefon else 0,
            email_sayisi=1 if t.email else 0,
            site_sayisi=1,
            siteler=[t.site_adi] if t.site_adi else [],
        )
        for t in tcsizler
    ]

    return SearchResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=(total + per_page - 1) // per_page,
    )


@router.get("/api/stats")
def get_tcsiz_stats(current_user: dict = Depends(get_current_user)):
    """TC'siz kayıt istatistikleri (önbellekten)"""
    stats = tcsiz_stats.get()
    return {
        "toplam": stats["toplam"],
        "site_sayisi": stats["site_sayisi"],
        "site_bazli": stats["site_bazli"],
    }
