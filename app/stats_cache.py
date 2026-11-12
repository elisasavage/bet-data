"""
Istatistik onbellegi.

26M satirlik tablolarda COUNT / GROUP BY her istekte calistirilmaz. Sonuc bellekte
tutulur; suresi dolunca arka planda yenilenir ve istek eski degeri aninda alir
(stale-while-revalidate). Yalnizca ilk yukleme bekletir; o da acilista isitilir.
"""

import threading
import time

from sqlalchemy import text

from app.database import engine

TTL_SECONDS = 300


class _Cache:
    def __init__(self, loader, ttl: int = TTL_SECONDS):
        self._loader = loader
        self._ttl = ttl
        self._value = None
        self._loaded_at = 0.0
        self._first_load = threading.Lock()
        self._refreshing = threading.Lock()

    def get(self) -> dict:
        value = self._value
        if value is None:
            with self._first_load:
                if self._value is None:
                    self._store(self._loader())
                return self._value
        if time.monotonic() - self._loaded_at > self._ttl:
            self.refresh_async()
        return value

    def refresh_async(self) -> None:
        if self._refreshing.acquire(blocking=False):
            threading.Thread(target=self._refresh, daemon=True).start()

    def _refresh(self) -> None:
        try:
            self._store(self._loader())
        except Exception as exc:  # noqa: BLE001
            # Eski deger gecerli kalir; bir sonraki istekte tekrar denenir.
            print("UYARI: istatistik onbellegi yenilenemedi: %s" % exc)
        finally:
            self._refreshing.release()

    def _store(self, value: dict) -> None:
        self._value = value
        self._loaded_at = time.monotonic()


def _load_kisi_stats() -> dict:
    with engine.connect() as conn:
        # Ayri ifadeler: her sayim kendi paralel worker'larini alir (tek ifadede
        # alt sorgular worker havuzunu paylasip seri taramaya dusuyor).
        toplam_kisi = conn.execute(text("select count(*) from kisiler")).scalar()
        toplam_telefon = conn.execute(text("select count(*) from telefonlar")).scalar()
        toplam_email = conn.execute(text("select count(*) from emailler")).scalar()
        # Tek GROUP BY: toplam uyelik, site sayisi, site listesi ve ilk 10 buradan turetilir.
        site_rows = conn.execute(text(
            "select site_adi, count(*) as adet from uyelikler group by site_adi"
        )).all()

    sirali = sorted(site_rows, key=lambda r: r.adet, reverse=True)
    site_counts = {r.site_adi: r.adet for r in site_rows if r.site_adi}
    return {
        "toplam_kisi": toplam_kisi,
        "toplam_telefon": toplam_telefon,
        "toplam_email": toplam_email,
        "toplam_uyelik": sum(r.adet for r in site_rows),
        "site_sayisi": sum(1 for r in site_rows if r.site_adi is not None),
        "en_cok_uyelik": [{"site_adi": r.site_adi, "count": r.adet} for r in sirali[:10]],
        "site_counts": site_counts,
        "siteler": sorted(site_counts),
    }


def _load_tcsiz_stats() -> dict:
    with engine.connect() as conn:
        rows = conn.execute(text(
            "select site_adi, count(*) as adet from tcsizler group by site_adi"
        )).all()
    return {
        "toplam": sum(r.adet for r in rows),
        "site_sayisi": len(rows),
        "site_bazli": [{"site_adi": r.site_adi, "count": r.adet} for r in rows],
        "site_counts": {r.site_adi: r.adet for r in rows if r.site_adi},
    }


kisi_stats = _Cache(_load_kisi_stats)
tcsiz_stats = _Cache(_load_tcsiz_stats)


def warm_in_background() -> None:
    """Acilista onbellegi isit; DB hazir degilse sessizce gec (ilk istek yukler)."""
    def _warm():
        for cache in (kisi_stats, tcsiz_stats):
            try:
                cache.get()
            except Exception as exc:  # noqa: BLE001
                print("UYARI: istatistik onbellegi isitilamadi: %s" % exc)

    threading.Thread(target=_warm, daemon=True).start()
