from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlmodel import Session, select

from .database import get_session, init_db
from .models import (
    Artist,
    Campaign,
    CampaignTask,
    CreativeAsset,
    Event,
    Manager,
    MetricSnapshot,
    Report,
)

app = FastAPI(title="RUVO Manager Platform", version="0.1.0")


@app.on_event("startup")
def on_startup() -> None:
    init_db()


# ---------- Schemas ---------- #


class ManagerCreate(BaseModel):
    name: str
    email: EmailStr
    company: Optional[str] = None


class ManagerRead(BaseModel):
    id: int
    name: str
    email: EmailStr
    company: Optional[str]

    class Config:
        orm_mode = True


class ArtistCreate(BaseModel):
    manager_id: int
    name: str
    genre: Optional[str] = None
    bio: Optional[str] = None
    social_links: Dict[str, str] = Field(default_factory=dict)


class ArtistUpdate(BaseModel):
    genre: Optional[str] = None
    bio: Optional[str] = None
    social_links: Optional[Dict[str, str]] = None


class ArtistRead(BaseModel):
    id: int
    manager_id: int
    name: str
    genre: Optional[str]
    bio: Optional[str]
    social_links: Dict[str, str]

    class Config:
        orm_mode = True


class AssetCreate(BaseModel):
    asset_type: str
    title: str
    description: Optional[str] = None
    url: Optional[str] = None
    attributes: Dict[str, str] = Field(default_factory=dict, alias="metadata")

    class Config:
        allow_population_by_field_name = True


class AssetResponse(BaseModel):
    id: str
    status: str
    url: str
    title: str
    metadata: Dict[str, str]


class CampaignCreate(BaseModel):
    name: str
    type: str
    goal: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class TaskCreate(BaseModel):
    title: str
    due_date: Optional[date] = None
    description: Optional[str] = None


class MetricCreate(BaseModel):
    source: str
    streams: Optional[int] = None
    followers: Optional[int] = None
    engagement_rate: Optional[float] = None
    top_cities: List[str] = Field(default_factory=list)
    notes: Optional[str] = None


class ReportRequest(BaseModel):
    period_start: date
    period_end: date


class ReportRead(BaseModel):
    id: int
    period_start: date
    period_end: date
    summary: str
    metrics: Dict[str, float]

    class Config:
        orm_mode = True


# ---------- Manager & Artist endpoints ---------- #


@app.post("/managers", response_model=ManagerRead, status_code=201)
def create_manager(payload: ManagerCreate, session: Session = Depends(get_session)) -> Manager:
    manager = Manager(**payload.dict())
    session.add(manager)
    session.commit()
    session.refresh(manager)
    return manager


@app.get("/managers/{manager_id}", response_model=ManagerRead)
def get_manager(manager_id: int, session: Session = Depends(get_session)) -> Manager:
    manager = session.get(Manager, manager_id)
    if not manager:
        raise HTTPException(status_code=404, detail="Manager not found")
    return manager


@app.post("/artists", response_model=ArtistRead, status_code=201)
def create_artist(payload: ArtistCreate, session: Session = Depends(get_session)) -> Artist:
    manager = session.get(Manager, payload.manager_id)
    if not manager:
        raise HTTPException(status_code=404, detail="Manager not found")
    artist = Artist(**payload.dict())
    session.add(artist)
    session.commit()
    session.refresh(artist)
    return artist


@app.get("/artists/{artist_id}", response_model=ArtistRead)
def get_artist(artist_id: int, session: Session = Depends(get_session)) -> Artist:
    artist = session.get(Artist, artist_id)
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")
    return artist


@app.patch("/artists/{artist_id}", response_model=ArtistRead)
def update_artist(artist_id: int, payload: ArtistUpdate, session: Session = Depends(get_session)) -> Artist:
    artist = session.get(Artist, artist_id)
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")
    update_data = payload.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(artist, field, value)
    session.add(artist)
    session.commit()
    session.refresh(artist)
    return artist


@app.get("/managers/{manager_id}/artists", response_model=List[ArtistRead])
def list_manager_artists(manager_id: int, session: Session = Depends(get_session)) -> List[Artist]:
    manager = session.get(Manager, manager_id)
    if not manager:
        raise HTTPException(status_code=404, detail="Manager not found")
    artists = session.exec(select(Artist).where(Artist.manager_id == manager_id)).all()
    return artists


# ---------- Creative tools ---------- #


@app.post("/artists/{artist_id}/assets", response_model=AssetResponse, status_code=201)
def create_asset(artist_id: int, payload: AssetCreate, session: Session = Depends(get_session)) -> AssetResponse:
    artist = session.get(Artist, artist_id)
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")
    asset = CreativeAsset(
        artist_id=artist_id,
        asset_type=payload.asset_type,
        title=payload.title,
        description=payload.description,
        url=payload.url,
        attributes=payload.attributes,
    )
    if asset.asset_type.lower() == "cover_art" and not asset.url:
        asset.url = (
            f"https://cdn.ruvo.ai/mock/cover-art/"
            f"{artist_id}-{asset.title.replace(' ', '-').lower()}"
        )
        asset.status = "generated"
        asset.attributes.setdefault("style", "vibrant")
        asset.attributes.setdefault("prompt", f"Cover art for {artist.name}")
    session.add(asset)
    session.commit()
    session.refresh(asset)
    return AssetResponse(
        id=str(asset.id),
        status=asset.status,
        url=asset.url or "",
        title=asset.title,
        metadata=asset.attributes,
    )


@app.post("/artists/{artist_id}/epk", response_model=Dict[str, object])
def generate_epk(artist_id: int, session: Session = Depends(get_session)) -> Dict[str, object]:
    artist = session.get(Artist, artist_id)
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")
    campaigns = session.exec(select(Campaign).where(Campaign.artist_id == artist_id)).all()
    latest_metrics = (
        session.exec(
            select(MetricSnapshot)
            .where(MetricSnapshot.artist_id == artist_id)
            .order_by(MetricSnapshot.captured_at.desc())
        ).first()
    )
    top_tracks = [campaign.name for campaign in campaigns[:3]]
    epk = {
        "artist": artist.name,
        "bio": artist.bio,
        "genre": artist.genre,
        "top_tracks": top_tracks,
        "social_links": artist.social_links,
        "latest_metrics": {
            "streams": latest_metrics.streams if latest_metrics else None,
            "followers": latest_metrics.followers if latest_metrics else None,
            "engagement_rate": latest_metrics.engagement_rate if latest_metrics else None,
        },
    }
    return epk


# ---------- Campaigns ---------- #


DEFAULT_TASKS = {
    "release": [
        ("Finalize cover art", -7),
        ("Distribute to DSPs", -10),
        ("Schedule social rollout", -5),
    ],
    "tour": [
        ("Confirm routing", -30),
        ("Announce on socials", -14),
        ("Email ticket buyers", -7),
    ],
}


@app.post("/artists/{artist_id}/campaigns", response_model=Dict[str, object], status_code=201)
def create_campaign(artist_id: int, payload: CampaignCreate, session: Session = Depends(get_session)) -> Dict[str, object]:
    artist = session.get(Artist, artist_id)
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")
    campaign = Campaign(artist_id=artist_id, **payload.dict())
    session.add(campaign)
    session.commit()
    session.refresh(campaign)

    auto_tasks: List[CampaignTask] = []
    blueprint = DEFAULT_TASKS.get(payload.type.lower(), [])
    for title, offset in blueprint:
        due_date = payload.start_date
        if due_date:
            due_date = due_date + timedelta(days=offset)
        task = CampaignTask(campaign_id=campaign.id, title=title, due_date=due_date)
        session.add(task)
        auto_tasks.append(task)
    session.commit()
    return {
        "id": campaign.id,
        "status": campaign.status,
        "auto_tasks": [task.title for task in auto_tasks],
    }


@app.post("/campaigns/{campaign_id}/tasks", response_model=Dict[str, object], status_code=201)
def add_campaign_task(campaign_id: int, payload: TaskCreate, session: Session = Depends(get_session)) -> Dict[str, object]:
    campaign = session.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    task = CampaignTask(campaign_id=campaign_id, **payload.dict())
    session.add(task)
    session.commit()
    session.refresh(task)
    return {
        "id": task.id,
        "title": task.title,
        "due_date": str(task.due_date) if task.due_date else None,
    }


@app.post("/campaigns/{campaign_id}/tasks/{task_id}/complete", response_model=Dict[str, object])
def complete_task(campaign_id: int, task_id: int, session: Session = Depends(get_session)) -> Dict[str, object]:
    task = session.get(CampaignTask, task_id)
    if not task or task.campaign_id != campaign_id:
        raise HTTPException(status_code=404, detail="Task not found")
    task.completed = True
    session.add(task)
    session.commit()
    return {"id": task.id, "completed": task.completed}


# ---------- Metrics & Insights ---------- #


@app.post("/artists/{artist_id}/metrics", response_model=Dict[str, object], status_code=201)
def add_metrics(artist_id: int, payload: MetricCreate, session: Session = Depends(get_session)) -> Dict[str, object]:
    artist = session.get(Artist, artist_id)
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")
    snapshot = MetricSnapshot(artist_id=artist_id, **payload.dict())
    session.add(snapshot)
    session.commit()
    session.refresh(snapshot)
    return {"id": snapshot.id, "captured_at": snapshot.captured_at.isoformat()}


@app.get("/artists/{artist_id}/dashboard", response_model=Dict[str, object])
def get_dashboard(artist_id: int, session: Session = Depends(get_session)) -> Dict[str, object]:
    artist = session.get(Artist, artist_id)
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")
    campaigns = session.exec(select(Campaign).where(Campaign.artist_id == artist_id)).all()
    campaign_ids = [campaign.id for campaign in campaigns]
    tasks: List[CampaignTask]
    if campaign_ids:
        tasks = session.exec(
            select(CampaignTask).where(CampaignTask.campaign_id.in_(campaign_ids))
        ).all()
    else:
        tasks = []
    metrics = session.exec(select(MetricSnapshot).where(MetricSnapshot.artist_id == artist_id)).all()
    total_streams = sum(m.streams or 0 for m in metrics)
    total_followers = max((m.followers or 0 for m in metrics), default=0)
    pending_tasks = [task for task in tasks if not task.completed]
    dashboard = {
        "artist": artist.name,
        "campaigns": [
            {"id": c.id, "name": c.name, "status": c.status, "type": c.type}
            for c in campaigns
        ],
        "pending_tasks": [
            {"id": t.id, "title": t.title, "due_date": str(t.due_date) if t.due_date else None}
            for t in pending_tasks
        ],
        "metrics_summary": {
            "total_streams": total_streams,
            "current_followers": total_followers,
            "latest_engagement_rate": metrics[-1].engagement_rate if metrics else None,
        },
    }
    return dashboard


@app.get("/artists/{artist_id}/recommendations", response_model=Dict[str, List[str]])
def get_recommendations(artist_id: int, session: Session = Depends(get_session)) -> Dict[str, List[str]]:
    artist = session.get(Artist, artist_id)
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")
    metrics = session.exec(
        select(MetricSnapshot)
        .where(MetricSnapshot.artist_id == artist_id)
        .order_by(MetricSnapshot.captured_at.desc())
    ).all()
    if not metrics:
        return {"recommendations": ["Add your first metric snapshot to unlock insights."]}

    latest = metrics[0]
    recs: List[str] = []
    if latest.top_cities:
        recs.append(
            f"Streams are strongest in {latest.top_cities[0]}; consider booking local shows or targeted ads there."
        )
    if latest.engagement_rate and latest.engagement_rate < 2.5:
        recs.append("Engagement is dipping—launch an interactive social campaign this week.")
    if latest.followers and latest.streams:
        ratio = latest.streams / max(latest.followers, 1)
        if ratio > 5_000:
            recs.append("High streams per follower—launch a merch drop to capture momentum.")
    if not recs:
        recs.append("Momentum looks healthy—schedule a press outreach sprint to widen exposure.")
    return {"recommendations": recs}


# ---------- Reporting ---------- #


@app.post("/artists/{artist_id}/reports", response_model=ReportRead, status_code=201)
def generate_report(artist_id: int, payload: ReportRequest, session: Session = Depends(get_session)) -> Report:
    artist = session.get(Artist, artist_id)
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")
    start_dt = datetime.combine(payload.period_start, datetime.min.time())
    end_dt = datetime.combine(payload.period_end, datetime.max.time())
    metrics = session.exec(
        select(MetricSnapshot)
        .where(MetricSnapshot.artist_id == artist_id)
        .where(MetricSnapshot.captured_at.between(start_dt, end_dt))
    ).all()
    total_streams = sum(metric.streams or 0 for metric in metrics)
    avg_engagement = (
        sum(metric.engagement_rate or 0 for metric in metrics) / len(metrics)
        if metrics
        else 0
    )
    summary = (
        f"{artist.name} generated {total_streams} streams between {payload.period_start} and {payload.period_end}. "
        f"Average engagement rate was {avg_engagement:.2f}% across {len(metrics)} data pulls."
    )
    report = Report(
        artist_id=artist_id,
        period_start=payload.period_start,
        period_end=payload.period_end,
        summary=summary,
        metrics={
            "total_streams": total_streams,
            "average_engagement": round(avg_engagement, 2),
            "data_points": len(metrics),
        },
    )
    session.add(report)
    session.commit()
    session.refresh(report)
    return report


@app.get("/artists/{artist_id}/reports", response_model=List[ReportRead])
def list_reports(artist_id: int, session: Session = Depends(get_session)) -> List[Report]:
    artist = session.get(Artist, artist_id)
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")
    reports = session.exec(select(Report).where(Report.artist_id == artist_id)).all()
    return reports


# ---------- Events ---------- #


class EventCreate(BaseModel):
    name: str
    event_type: str
    date: date
    location: Optional[str] = None
    notes: Optional[str] = None


class EventRead(BaseModel):
    id: int
    name: str
    event_type: str
    date: date
    location: Optional[str]
    notes: Optional[str]

    class Config:
        orm_mode = True


@app.post("/artists/{artist_id}/events", response_model=EventRead, status_code=201)
def create_event(artist_id: int, payload: EventCreate, session: Session = Depends(get_session)) -> Event:
    artist = session.get(Artist, artist_id)
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")
    event = Event(artist_id=artist_id, **payload.dict())
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


@app.get("/artists/{artist_id}/events", response_model=List[EventRead])
def list_events(artist_id: int, session: Session = Depends(get_session)) -> List[Event]:
    artist = session.get(Artist, artist_id)
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")
    events = session.exec(select(Event).where(Event.artist_id == artist_id)).all()
    return events
