import os
import sys
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from app.main import app

DB_PATH = "ruvo.db"


def setup_module(module):  # noqa: D401
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_end_to_end_manager_artist_flow(client):
    manager_payload = {"name": "Jordan", "email": "jordan@example.com", "company": "RUVO"}
    manager_resp = client.post("/managers", json=manager_payload)
    assert manager_resp.status_code == 201
    manager_id = manager_resp.json()["id"]

    artist_payload = {
        "manager_id": manager_id,
        "name": "Nova",
        "genre": "Pop",
        "bio": "Independent artist",
        "social_links": {"instagram": "@nova"},
    }
    artist_resp = client.post("/artists", json=artist_payload)
    assert artist_resp.status_code == 201
    artist_id = artist_resp.json()["id"]

    metric_payload = {
        "source": "Spotify",
        "streams": 120000,
        "followers": 2200,
        "engagement_rate": 1.8,
        "top_cities": ["Chicago", "Denver"],
    }
    metric_resp = client.post(f"/artists/{artist_id}/metrics", json=metric_payload)
    assert metric_resp.status_code == 201

    campaign_payload = {
        "name": "Nova Rising",
        "type": "release",
        "goal": "Grow monthly listeners",
        "start_date": date.today().isoformat(),
    }
    campaign_resp = client.post(f"/artists/{artist_id}/campaigns", json=campaign_payload)
    assert campaign_resp.status_code == 201
    assert len(campaign_resp.json()["auto_tasks"]) == 3

    asset_payload = {"asset_type": "cover_art", "title": "Nova Rising"}
    asset_resp = client.post(f"/artists/{artist_id}/assets", json=asset_payload)
    assert asset_resp.status_code == 201
    assert asset_resp.json()["status"] == "generated"

    event_payload = {
        "name": "Album Launch",
        "event_type": "release",
        "date": date.today().isoformat(),
        "location": "Chicago",
    }
    event_resp = client.post(f"/artists/{artist_id}/events", json=event_payload)
    assert event_resp.status_code == 201

    dashboard = client.get(f"/artists/{artist_id}/dashboard").json()
    assert dashboard["artist"] == "Nova"
    assert dashboard["metrics_summary"]["total_streams"] == 120000
    assert dashboard["pending_tasks"], "Expected pending tasks to be present"

    epk = client.post(f"/artists/{artist_id}/epk").json()
    assert epk["artist"] == "Nova"
    assert epk["latest_metrics"]["streams"] == 120000

    report_payload = {
        "period_start": date.today().replace(day=1).isoformat(),
        "period_end": date.today().isoformat(),
    }
    report_resp = client.post(f"/artists/{artist_id}/reports", json=report_payload)
    assert report_resp.status_code == 201
    assert "generated" in report_resp.json()["summary"]

    recommendations = client.get(f"/artists/{artist_id}/recommendations").json()
    assert recommendations["recommendations"], "Expected at least one recommendation"
