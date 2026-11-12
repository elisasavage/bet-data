"""
Pydantic şemaları - API request/response modelleri
"""

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


# ============ Telefon ============
class TelefonBase(BaseModel):
    telefon: str


class TelefonResponse(TelefonBase):
    id: int
    
    class Config:
        from_attributes = True


# ============ Email ============
class EmailBase(BaseModel):
    email: str


class EmailResponse(EmailBase):
    id: int
    
    class Config:
        from_attributes = True


# ============ Üyelik ============
class UyelikBase(BaseModel):
    site_adi: str
    kaynak_dosya: Optional[str] = None


class UyelikResponse(UyelikBase):
    id: int
    
    class Config:
        from_attributes = True


# ============ Kişi ============
class KisiBase(BaseModel):
    tc: str
    isim: Optional[str] = None
    soyisim: Optional[str] = None


class KisiCreate(KisiBase):
    telefonlar: Optional[List[str]] = []
    emailler: Optional[List[str]] = []
    uyelikler: Optional[List[UyelikBase]] = []


class KisiResponse(KisiBase):
    id: int
    created_at: Optional[datetime] = None
    telefonlar: List[TelefonResponse] = []
    emailler: List[EmailResponse] = []
    uyelikler: List[UyelikResponse] = []
    
    class Config:
        from_attributes = True


class KisiListResponse(BaseModel):
    id: int
    tc: str
    isim: Optional[str] = None
    soyisim: Optional[str] = None
    telefon_sayisi: int = 0
    email_sayisi: int = 0
    site_sayisi: int = 0
    siteler: List[str] = []
    
    class Config:
        from_attributes = True


# ============ Arama/Filtreleme ============
class SearchParams(BaseModel):
    query: Optional[str] = None  # TC, isim veya telefon
    site: Optional[str] = None   # Site filtresi
    page: int = 1
    per_page: int = 50


class SearchResponse(BaseModel):
    items: List[KisiListResponse]
    total: int
    page: int
    per_page: int
    total_pages: int


# ============ İstatistikler ============
class StatsResponse(BaseModel):
    toplam_kisi: int
    toplam_telefon: int
    toplam_email: int
    toplam_uyelik: int
    site_sayisi: int
    en_cok_uyelik: List[dict]  # [{site_adi, count}]


# ============ Auth ============
class LoginRequest(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
