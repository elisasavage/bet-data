"""
Kişi CRUD işlemleri
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List

from app.database import get_db
from app.models import Kisi, Telefon, Email, Uyelik
from app.schemas import KisiResponse, KisiCreate, KisiListResponse, StatsResponse
from app.auth import get_current_user

router = APIRouter(prefix="/api/kisiler", tags=["Kisiler"])


@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """İstatistikleri getir"""
    toplam_kisi = db.query(func.count(Kisi.id)).scalar()
    toplam_telefon = db.query(func.count(Telefon.id)).scalar()
    toplam_email = db.query(func.count(Email.id)).scalar()
    toplam_uyelik = db.query(func.count(Uyelik.id)).scalar()
    
    # Benzersiz site sayısı
    site_sayisi = db.query(func.count(func.distinct(Uyelik.site_adi))).scalar()
    
    # En çok üyelik olan siteler
    en_cok_uyelik = db.query(
        Uyelik.site_adi,
        func.count(Uyelik.id).label('count')
    ).group_by(Uyelik.site_adi).order_by(func.count(Uyelik.id).desc()).limit(10).all()
    
    return StatsResponse(
        toplam_kisi=toplam_kisi or 0,
        toplam_telefon=toplam_telefon or 0,
        toplam_email=toplam_email or 0,
        toplam_uyelik=toplam_uyelik or 0,
        site_sayisi=site_sayisi or 0,
        en_cok_uyelik=[{"site_adi": s[0], "count": s[1]} for s in en_cok_uyelik]
    )


@router.get("/{kisi_id}", response_model=KisiResponse)
async def get_kisi(
    kisi_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Kişi detaylarını getir"""
    kisi = db.query(Kisi).filter(Kisi.id == kisi_id).first()
    if not kisi:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kişi bulunamadı"
        )
    return kisi


@router.get("/tc/{tc}", response_model=KisiResponse)
async def get_kisi_by_tc(
    tc: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """TC ile kişi getir"""
    kisi = db.query(Kisi).filter(Kisi.tc == tc).first()
    if not kisi:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kişi bulunamadı"
        )
    return kisi


@router.get("/siteler/liste", response_model=List[str])
async def get_siteler(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Tüm siteleri listele"""
    siteler = db.query(func.distinct(Uyelik.site_adi)).all()
    return [s[0] for s in siteler if s[0]]
