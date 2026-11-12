"""
Arama ve filtreleme işlemleri

Performans notlari:
- Uclar `def`: senkron DB cagrilari thread havuzunda calisir, paneli kilitlemez.
- Isim aramasi tek ifade uzerinden yapilir; bu ifade pg_trgm GIN index'i
  (idx_kisiler_adsoyad_trgm) ile birebir ayni olmalidir, yoksa index kullanilmaz.
- Sayfadaki kisilerin telefon/email/site bilgisi kisi basina degil, 3 toplu
  sorguyla cekilir (N+1 yok).
- Filtresiz ve yalniz-site toplamlar onbellekten gelir.
"""

from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, literal_column, select, union
from sqlalchemy.orm import Session, aliased

from app.database import get_db
from app.models import Kisi, Telefon, Email, Uyelik
from app.schemas import SearchResponse, KisiListResponse
from app.auth import get_current_user
from app.stats_cache import kisi_stats

router = APIRouter(prefix="/api/search", tags=["Search"])

# idx_kisiler_adsoyad_trgm index ifadesiyle ayni. concat(isim,' ',soyisim) ile
# esdegerdir; tek tek isim/soyisim eslesmelerini de kapsar.
AD_SOYAD = literal_column("(coalesce(kisiler.isim,'') || ' ' || coalesce(kisiler.soyisim,''))")


def _build_filters(q: Optional[str], site: Optional[str]) -> list:
    filters = []

    if q:
        search_term = f"%{q}%"
        if q.isdigit() and len(q) == 11:
            # TC tam eşleşme
            filters.append(Kisi.tc == q)
        elif q.isdigit():
            # TC parçası veya telefon. UNION: iki trigram index'i ayri ayri kullanilir
            # (OR + alt sorgu tam tablo taramasina dusuyordu).
            k2 = aliased(Kisi)
            eslesen = union(
                select(k2.id).where(k2.tc.like(search_term)),
                select(Telefon.kisi_id).where(Telefon.telefon.like(search_term)),
            )
            filters.append(Kisi.id.in_(eslesen))
        else:
            # İsim/soyisim araması
            filters.append(AD_SOYAD.ilike(search_term))

    if site:
        filters.append(
            select(Uyelik.id)
            .where(Uyelik.kisi_id == Kisi.id, Uyelik.site_adi == site)
            .exists()
        )

    return filters


def _count(db: Session, filters: list, q: Optional[str], site: Optional[str]) -> int:
    if not q:
        stats = kisi_stats.get()
        if not site:
            return stats["toplam_kisi"]
        # (kisi_id, site_adi) unique: sitedeki uyelik sayisi = sitedeki kisi sayisi.
        cached = stats["site_counts"].get(site)
        if cached is not None:
            return cached
    return db.execute(select(func.count()).select_from(Kisi).where(*filters)).scalar() or 0


def _search(db: Session, q: Optional[str], site: Optional[str], page: int, per_page: int) -> SearchResponse:
    filters = _build_filters(q, site)
    total = _count(db, filters, q, site)

    kisiler = db.execute(
        select(Kisi.id, Kisi.tc, Kisi.isim, Kisi.soyisim)
        .where(*filters)
        .order_by(Kisi.id)
        .offset((page - 1) * per_page)
        .limit(per_page)
    ).all()

    ids = [k.id for k in kisiler]
    siteler: dict = defaultdict(list)
    telefon_sayisi: dict = {}
    email_sayisi: dict = {}

    if ids:
        for kisi_id, site_adi in db.execute(
            select(Uyelik.kisi_id, Uyelik.site_adi)
            .where(Uyelik.kisi_id.in_(ids))
            .order_by(Uyelik.kisi_id, Uyelik.id)
        ):
            if site_adi is not None:
                siteler[kisi_id].append(site_adi)
        telefon_sayisi = dict(db.execute(
            select(Telefon.kisi_id, func.count())
            .where(Telefon.kisi_id.in_(ids))
            .group_by(Telefon.kisi_id)
        ).all())
        email_sayisi = dict(db.execute(
            select(Email.kisi_id, func.count())
            .where(Email.kisi_id.in_(ids))
            .group_by(Email.kisi_id)
        ).all())

    items = [
        KisiListResponse(
            id=k.id,
            tc=k.tc,
            isim=k.isim,
            soyisim=k.soyisim,
            telefon_sayisi=telefon_sayisi.get(k.id, 0),
            email_sayisi=email_sayisi.get(k.id, 0),
            site_sayisi=len(siteler[k.id]),
            siteler=siteler[k.id],
        )
        for k in kisiler
    ]

    return SearchResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=(total + per_page - 1) // per_page,
    )


@router.get("", response_model=SearchResponse)
def search_kisiler(
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
    return _search(db, q, site, page, per_page)


@router.get("/by-site/{site_adi}", response_model=SearchResponse)
def get_kisiler_by_site(
    site_adi: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Belirli bir siteye üye kişileri getir
    """
    return _search(db, None, site_adi, page, per_page)
