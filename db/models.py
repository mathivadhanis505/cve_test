from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime

Base = declarative_base()


class Run(Base):
    __tablename__ = "runs"

    id = Column(Integer, primary_key=True, index=True)

    started_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)

    repos_scanned = Column(Integer, default=0)
    patches_opened = Column(Integer, default=0)
    patches_merged = Column(Integer, default=0)

    cves = relationship(
        "CVE",
        back_populates="run",
        cascade="all, delete-orphan"
    )

    patches = relationship(
        "Patch",
        back_populates="run",
        cascade="all, delete-orphan"
    )


class CVE(Base):
    __tablename__ = "cves"

    id = Column(Integer, primary_key=True, index=True)

    repo = Column(String, index=True, nullable=False)
    package = Column(String, index=True, nullable=False)
    severity = Column(String, nullable=False)

    installed_version = Column(String)
    fixed_version = Column(String)

    scanned_at = Column(DateTime, default=datetime.utcnow)

    run_id = Column(
        Integer,
        ForeignKey("runs.id"),
        nullable=False
    )

    run = relationship("Run", back_populates="cves")

    patches = relationship(
        "Patch",
        back_populates="cve",
        cascade="all, delete-orphan"
    )


class Patch(Base):
    __tablename__ = "patches"

    id = Column(Integer, primary_key=True, index=True)

    cve_id = Column(
        Integer,
        ForeignKey("cves.id"),
        nullable=False
    )

    run_id = Column(
        Integer,
        ForeignKey("runs.id"),
        nullable=False
    )

    branch_name = Column(String)
    pr_url = Column(String)

    status = Column(
        String,
        nullable=False,
        index=True
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    cve = relationship("CVE", back_populates="patches")
    run = relationship("Run", back_populates="patches")

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'testing', 'merged', 'failed')",
            name="valid_patch_status"
        ),
    )
