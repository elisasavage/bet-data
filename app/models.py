"""
SQLAlchemy ORM modelleri
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Kisi(Base):
    """Kişi tablosu - TC bazlı unique kayıtlar"""
    __tablename__ = "kisiler"
    
    id = Column(Integer, primary_key=True, index=True)
    tc = Column(String(11), unique=True, index=True, nullable=False)
    isim = Column(String(100))
    soyisim = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # İlişkiler
    telefonlar = relationship("Telefon", back_populates="kisi", cascade="all, delete-orphan")
    emailler = relationship("Email", back_populates="kisi", cascade="all, delete-orphan")
    uyelikler = relationship("Uyelik", back_populates="kisi", cascade="all, delete-orphan")
    
    # Full-text search için index
    __table_args__ = (
        Index('idx_kisi_isim_soyisim', 'isim', 'soyisim'),
    )


class Telefon(Base):
    """Telefon numaraları - bir kişinin birden fazla olabilir"""
    __tablename__ = "telefonlar"
    
    id = Column(Integer, primary_key=True, index=True)
    kisi_id = Column(Integer, ForeignKey("kisiler.id", ondelete="CASCADE"), nullable=False)
    telefon = Column(String(20), index=True)
    
    kisi = relationship("Kisi", back_populates="telefonlar")
    
    __table_args__ = (
        Index('idx_telefon_unique', 'kisi_id', 'telefon', unique=True),
    )


class Email(Base):
    """Email adresleri"""
    __tablename__ = "emailler"
    
    id = Column(Integer, primary_key=True, index=True)
    kisi_id = Column(Integer, ForeignKey("kisiler.id", ondelete="CASCADE"), nullable=False)
    email = Column(String(255), index=True)
    
    kisi = relationship("Kisi", back_populates="emailler")
    
    __table_args__ = (
        Index('idx_email_unique', 'kisi_id', 'email', unique=True),
    )


class Uyelik(Base):
    """Üyelikler - hangi sitelerde kayıtlı"""
    __tablename__ = "uyelikler"
    
    id = Column(Integer, primary_key=True, index=True)
    kisi_id = Column(Integer, ForeignKey("kisiler.id", ondelete="CASCADE"), nullable=False)
    site_adi = Column(String(100), index=True)
    kaynak_dosya = Column(String(255))
    
    kisi = relationship("Kisi", back_populates="uyelikler")
    
    __table_args__ = (
        Index('idx_uyelik_unique', 'kisi_id', 'site_adi', unique=True),
    )


class Tcsiz(Base):
    """TC'si olmayan kayıtlar"""
    __tablename__ = "tcsizler"
    
    id = Column(Integer, primary_key=True, index=True)
    isim = Column(String(100))
    soyisim = Column(String(100))
    telefon = Column(String(20), index=True)
    email = Column(String(255), index=True)
    site_adi = Column(String(100), index=True)
    kaynak_dosya = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    __table_args__ = (
        Index('idx_tcsiz_isim_soyisim', 'isim', 'soyisim'),
        Index('idx_tcsiz_unique', 'isim', 'soyisim', 'telefon', 'email', 'site_adi', unique=True),
    )
