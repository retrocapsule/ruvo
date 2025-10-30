from __future__ import annotations

from datetime import date, datetime
from typing import Dict, List, Optional

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel


class Manager(SQLModel, table=True):
    __tablename__ = "managers"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    email: str
    company: Optional[str] = None


class Artist(SQLModel, table=True):
    __tablename__ = "artists"

    id: Optional[int] = Field(default=None, primary_key=True)
    manager_id: int = Field(foreign_key="managers.id")
    name: str
    genre: Optional[str] = None
    bio: Optional[str] = None
    social_links: Dict[str, str] = Field(default_factory=dict, sa_column=Column(JSON))


class Campaign(SQLModel, table=True):
    __tablename__ = "campaigns"

    id: Optional[int] = Field(default=None, primary_key=True)
    artist_id: int = Field(foreign_key="artists.id")
    name: str
    type: str
    goal: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: str = Field(default="planned")


class CampaignTask(SQLModel, table=True):
    __tablename__ = "campaign_tasks"

    id: Optional[int] = Field(default=None, primary_key=True)
    campaign_id: int = Field(foreign_key="campaigns.id")
    title: str
    due_date: Optional[date] = None
    description: Optional[str] = None
    completed: bool = Field(default=False)


class CreativeAsset(SQLModel, table=True):
    __tablename__ = "creative_assets"

    id: Optional[int] = Field(default=None, primary_key=True)
    artist_id: int = Field(foreign_key="artists.id")
    asset_type: str
    title: str
    description: Optional[str] = None
    status: str = Field(default="draft")
    url: Optional[str] = None
    attributes: Dict[str, str] = Field(default_factory=dict, sa_column=Column(JSON))


class Report(SQLModel, table=True):
    __tablename__ = "reports"

    id: Optional[int] = Field(default=None, primary_key=True)
    artist_id: int = Field(foreign_key="artists.id")
    period_start: date
    period_end: date
    summary: str
    metrics: Dict[str, float] = Field(default_factory=dict, sa_column=Column(JSON))
    delivered_at: datetime = Field(default_factory=datetime.utcnow)


class Event(SQLModel, table=True):
    __tablename__ = "events"

    id: Optional[int] = Field(default=None, primary_key=True)
    artist_id: int = Field(foreign_key="artists.id")
    name: str
    event_type: str
    date: date
    location: Optional[str] = None
    notes: Optional[str] = None


class MetricSnapshot(SQLModel, table=True):
    __tablename__ = "metric_snapshots"

    id: Optional[int] = Field(default=None, primary_key=True)
    artist_id: int = Field(foreign_key="artists.id")
    captured_at: datetime = Field(default_factory=datetime.utcnow)
    source: str
    streams: Optional[int] = None
    followers: Optional[int] = None
    engagement_rate: Optional[float] = None
    top_cities: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    notes: Optional[str] = None

