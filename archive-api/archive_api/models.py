"""SQLAlchemy ORM models for the exoplanet archive."""

import datetime

from sqlalchemy import Float, Index, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Exoplanet(Base):
    """Confirmed exoplanet with key physical and orbital parameters.

    Column names mirror the NASA Exoplanet Archive's Planetary Systems
    composite table (PS) where practical.
    """

    __tablename__ = "exoplanets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pl_name: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    hostname: Mapped[str] = mapped_column(String, nullable=False, index=True)
    discovery_method: Mapped[str] = mapped_column(String, nullable=False, index=True)
    disc_year: Mapped[int | None] = mapped_column(Integer, index=True)
    orbital_period: Mapped[float | None] = mapped_column(Float)
    pl_rade: Mapped[float | None] = mapped_column(Float)
    pl_bmasse: Mapped[float | None] = mapped_column(Float)
    pl_eqt: Mapped[float | None] = mapped_column(Float)
    st_teff: Mapped[float | None] = mapped_column(Float)
    st_rad: Mapped[float | None] = mapped_column(Float)
    sy_dist: Mapped[float | None] = mapped_column(Float)
    ra: Mapped[float | None] = mapped_column(Float)
    dec: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime.datetime] = mapped_column(
        server_default=func.now(),
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index("ix_disc_method_year", "discovery_method", "disc_year"),
    )

    def __repr__(self) -> str:
        return f"<Exoplanet {self.pl_name}>"
