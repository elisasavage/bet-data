"""
Kişi CRUD işlemleri

Not: uclar bilerek `def` (async degil). SQLAlchemy senkron calisir; `async def`
icinde cagrilirsa tek bir yavas sorgu butun paneli kilitler. `def` uclari FastAPI
thread havuzunda calistirir, istekler birbirini beklemez.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, selectinload
from typing import List

from app.database import get_db
from app.models import Kisi
from app.schemas import KisiResponse, StatsResponse
from app.auth import get_current_user
from app.stats_cache import kisi_stats

router = APIRouter(prefix="/api/kisiler", tags=["Kisiler"])

_DETAY = (
    selectinload(Kisi.telefonlar),
    selectinload(Kisi.emailler),
    selectinload(Kisi.uyelikler),
)


@router.get("/stats", response_model=StatsResponse)
def get_stats(current_user: dict = Depends(get_current_user)):
    """İstatistikleri getir (önbellekten)"""
    stats = kisi_stats.get()
    return StatsResponse(
        toplam_kisi=stats["toplam_kisi"],
        toplam_telefon=stats["toplam_telefon"],
        toplam_email=stats["toplam_email"],
        toplam_uyelik=stats["toplam_uyelik"],
        site_sayisi=stats["site_sayisi"],
        en_cok_uyelik=stats["en_cok_uyelik"],
    )


@router.get("/{kisi_id}", response_model=KisiResponse)
def get_kisi(
    kisi_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Kişi detaylarını getir"""
    kisi = db.query(Kisi).options(*_DETAY).filter(Kisi.id == kisi_id).first()
    if not kisi:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kişi bulunamadı"
        )
    return kisi


@router.get("/tc/{tc}", response_model=KisiResponse)
def get_kisi_by_tc(
    tc: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """TC ile kişi getir"""
    kisi = db.query(Kisi).options(*_DETAY).filter(Kisi.tc == tc).first()
    if not kisi:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kişi bulunamadı"
        )
    return kisi


@router.get("/siteler/liste", response_model=List[str])
def get_siteler(current_user: dict = Depends(get_current_user)):
    """Tüm siteleri listele (önbellekten)"""
    return kisi_stats.get()["siteler"]
