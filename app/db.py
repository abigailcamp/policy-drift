from datetime import date, datetime

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    text,
)
from sqlalchemy.orm import DeclarativeBase, relationship, sessionmaker

from app.config import DATABASE_URL


class Base(DeclarativeBase):
    pass


class Instrument(Base):
    __tablename__ = "instruments"

    id = Column(Integer, primary_key=True)
    slug = Column(String(120), unique=True, nullable=False)
    title = Column(String(500), nullable=False)
    instrument_type = Column(String(50), nullable=False)  # executive_order, public_law, statute
    policy_tags = Column(String(255), nullable=False, default="")
    source_ref = Column(String(120), nullable=False, default="")  # e.g. EO 14024, PL 118-50
    last_fetch_at = Column(DateTime, nullable=True)
    last_fetch_status = Column(String(20), nullable=True)  # ok, failed, manual
    last_fetch_message = Column(String(500), nullable=True)

    versions = relationship("Version", back_populates="instrument", order_by="Version.effective_date.desc()")


class Version(Base):
    __tablename__ = "versions"

    id = Column(Integer, primary_key=True)
    instrument_id = Column(Integer, ForeignKey("instruments.id"), nullable=False)
    version_label = Column(String(200), nullable=False)
    effective_date = Column(Date, nullable=True)
    normalized_text = Column(Text, nullable=False)
    content_hash = Column(String(64), nullable=False)
    fetch_status = Column(String(20), nullable=False, default="manual")  # manual, ok, failed

    instrument = relationship("Instrument", back_populates="versions")
    sources = relationship("VersionSource", back_populates="version")

    __table_args__ = (UniqueConstraint("instrument_id", "content_hash", name="uq_instrument_hash"),)


class VersionSource(Base):
    __tablename__ = "version_sources"

    id = Column(Integer, primary_key=True)
    version_id = Column(Integer, ForeignKey("versions.id"), nullable=False)
    source_url = Column(String(1000), nullable=False)
    source_type = Column(String(50), nullable=False)  # federal_register, govinfo, manual
    retrieved_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    version = relationship("Version", back_populates="sources")


class VersionPair(Base):
    __tablename__ = "version_pairs"

    id = Column(Integer, primary_key=True)
    from_version_id = Column(Integer, ForeignKey("versions.id"), nullable=False)
    to_version_id = Column(Integer, ForeignKey("versions.id"), nullable=False)
    diff_html_cached = Column(Text, nullable=True)
    diff_stats_json = Column(String(500), nullable=True)
    diff_mode = Column(String(20), nullable=False, default="unified")  # unified, side_by_side

    from_version = relationship("Version", foreign_keys=[from_version_id])
    to_version = relationship("Version", foreign_keys=[to_version_id])
    note = relationship("AnalystNote", back_populates="version_pair", uselist=False)

    __table_args__ = (UniqueConstraint("from_version_id", "to_version_id", name="uq_version_pair"),)


class AnalystNote(Base):
    __tablename__ = "analyst_notes"

    id = Column(Integer, primary_key=True)
    version_pair_id = Column(Integer, ForeignKey("version_pairs.id"), unique=True, nullable=False)
    summary = Column(Text, nullable=False, default="")
    policy_implications = Column(Text, nullable=False, default="")
    tags = Column(String(255), nullable=False, default="")
    caveats = Column(Text, nullable=False, default="")
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    version_pair = relationship("VersionPair", back_populates="note")


class Subscriber(Base):
    __tablename__ = "subscribers"

    id = Column(Integer, primary_key=True)
    instrument_id = Column(Integer, ForeignKey("instruments.id"), nullable=False)
    email = Column(String(320), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    instrument = relationship("Instrument")

    __table_args__ = (UniqueConstraint("instrument_id", "email", name="uq_subscriber_instrument_email"),)


connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def _migrate_schema() -> None:
    """Add columns introduced after first release (SQLite)."""
    with engine.connect() as conn:
        rows = conn.execute(text("PRAGMA table_info(instruments)")).fetchall()
        colnames = {row[1] for row in rows}
        if "last_fetch_message" not in colnames:
            conn.execute(text("ALTER TABLE instruments ADD COLUMN last_fetch_message VARCHAR(500)"))
            conn.commit()

        # Subscribers table (added later) is created by metadata; no ALTER needed.


def init_db() -> None:
    from app.config import PROJECT_ROOT

    (PROJECT_ROOT / "data").mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    _migrate_schema()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
