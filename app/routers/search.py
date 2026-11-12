"""
Arama ve filtreleme işlemleri
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, distinct
from typing import Optional, List

from app.database import get_db
from app.models import Kisi, Telefon, Email, Uyelik
from app.schemas import SearchResponse, KisiListResponse
from app.auth import get_current_user

router = APIRouter(prefix="/api/search", tags=["Search"])


@router.get("", response_model=SearchResponse)
async def search_kisiler(
    q: Optional[str] = Query(None, description="TC, isim, soyisim veya telefon"),
    site: Optional[str] = Query(None, description="Site filtresi"),
    page: int = Query(1, ge=1),
    per_page: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Kişileri ara ve filtrele - varsayılan olarak tüm listeyi gösterir
    """
    # Base query
    query = db.query(Kisi)
    
    # Text search (opsiyonel - boşsa tüm liste gelir)
    if q:
        search_term = f"%{q}%"
        # TC tam eşleşme veya like
        if q.isdigit() and len(q) == 11:
            query = query.filter(Kisi.tc == q)
        elif q.isdigit():
            # Telefon araması
            subquery = db.query(Telefon.kisi_id).filter(
                Telefon.telefon.like(search_term)
            ).distinct()
            query = query.filter(
                or_(
                    Kisi.tc.like(search_term),
                    Kisi.id.in_(subquery)
                )
            )
        else:
            # İsim/soyisim araması
            query = query.filter(
                or_(
                    Kisi.isim.ilike(search_term),
                    Kisi.soyisim.ilike(search_term),
                    func.concat(Kisi.isim, ' ', Kisi.soyisim).ilike(search_term)
                )
            )
    
    # Site filtresi
    if site:
        subquery = db.query(Uyelik.kisi_id).filter(
            Uyelik.site_adi == site
        ).distinct()
        query = query.filter(Kisi.id.in_(subquery))
    
    # Toplam sayı
    total = query.count()
    
    # Pagination
    offset = (page - 1) * per_page
    kisiler = query.offset(offset).limit(per_page).all()
    
    # Response oluştur
    items = []
    for kisi in kisiler:
        siteler = [u.site_adi for u in kisi.uyelikler]
        items.append(KisiListResponse(
            id=kisi.id,
            tc=kisi.tc,
            isim=kisi.isim,
            soyisim=kisi.soyisim,
            telefon_sayisi=len(kisi.telefonlar),
            email_sayisi=len(kisi.emailler),
            site_sayisi=len(kisi.uyelikler),
            siteler=siteler
        ))
    
    total_pages = (total + per_page - 1) // per_page
    
    return SearchResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages
    )


@router.get("/by-site/{site_adi}", response_model=SearchResponse)
async def get_kisiler_by_site(
    site_adi: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Belirli bir siteye üye kişileri getir
    """
    subquery = db.query(Uyelik.kisi_id).filter(
        Uyelik.site_adi == site_adi
    ).distinct()
    
    query = db.query(Kisi).filter(Kisi.id.in_(subquery))
    
    total = query.count()
    offset = (page - 1) * per_page
    kisiler = query.offset(offset).limit(per_page).all()
    
    items = []
    for kisi in kisiler:
        siteler = [u.site_adi for u in kisi.uyelikler]
        items.append(KisiListResponse(
            id=kisi.id,
            tc=kisi.tc,
            isim=kisi.isim,
            soyisim=kisi.soyisim,
            telefon_sayisi=len(kisi.telefonlar),
            email_sayisi=len(kisi.emailler),
            site_sayisi=len(kisi.uyelikler),
            siteler=siteler
        ))
    
    total_pages = (total + per_page - 1) // per_page
    
    return SearchResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages
    )
