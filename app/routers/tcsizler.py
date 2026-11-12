"""
TC'siz kayıtlar için router
"""

from fastapi import APIRouter, Depends, Query, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from typing import Optional
from pathlib import Path

from app.database import get_db
from app.models import Tcsiz
from app.auth import get_current_user, get_optional_user
from app.schemas import SearchResponse, KisiListResponse

router = APIRouter(prefix="/tcsizler", tags=["TC'sizler"])

BASE_PATH = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=str(BASE_PATH / "templates"))


@router.get("", response_class=HTMLResponse)
async def tcsizler_page(request: Request):
    """TC'sizler sayfası"""
    user = await get_optional_user(request)
    if not user:
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(request, "tcsizler.html")


@router.get("/api/list")
async def get_tcsizler(
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
    # Base query
    query = db.query(Tcsiz)
    
    # Text search
    if q:
        search_term = f"%{q}%"
        query = query.filter(
            or_(
                Tcsiz.isim.ilike(search_term),
                Tcsiz.soyisim.ilike(search_term),
                Tcsiz.telefon.like(search_term),
                func.concat(Tcsiz.isim, ' ', Tcsiz.soyisim).ilike(search_term)
            )
        )
    
    # Site filtresi
    if site:
        query = query.filter(Tcsiz.site_adi == site)
    
    # Toplam sayı
    total = query.count()
    
    # Pagination
    offset = (page - 1) * per_page
    tcsizler = query.order_by(Tcsiz.created_at.desc()).offset(offset).limit(per_page).all()
    
    # Response oluştur
    items = []
    for tcsiz in tcsizler:
        items.append(KisiListResponse(
            id=tcsiz.id,
            tc="",  # TC yok
            isim=tcsiz.isim,
            soyisim=tcsiz.soyisim,
            telefon_sayisi=1 if tcsiz.telefon else 0,
            email_sayisi=1 if tcsiz.email else 0,
            site_sayisi=1,
            siteler=[tcsiz.site_adi] if tcsiz.site_adi else []
        ))
    
    total_pages = (total + per_page - 1) // per_page
    
    return SearchResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages
    )


@router.get("/api/stats")
async def get_tcsiz_stats(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """TC'siz kayıt istatistikleri"""
    total = db.query(func.count(Tcsiz.id)).scalar()
    
    # Site bazlı sayılar
    site_counts = db.query(
        Tcsiz.site_adi,
        func.count(Tcsiz.id).label('count')
    ).group_by(Tcsiz.site_adi).all()
    
    return {
        "toplam": total,
        "site_sayisi": len(site_counts),
        "site_bazli": [{"site_adi": site, "count": count} for site, count in site_counts]
    }
