"""Tests for the FastAPI dashboard."""

import pytest
from fastapi.testclient import TestClient

from lodestar.config import Settings
from lodestar.dashboard.app import create_app


@pytest.fixture
def client():
    settings = Settings()
    app = create_app(settings)
    return TestClient(app)


def test_index_page(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Lodestar" in resp.text


def test_api_status_no_bot(client):
    resp = client.get("/api/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "not running"


def test_api_positions_no_bot(client):
    resp = client.get("/api/positions")
    assert resp.status_code == 200
    assert resp.json() == []


def test_api_trades_no_bot(client):
    resp = client.get("/api/trades")
    assert resp.status_code == 200
    assert resp.json() == []


def test_api_signals_no_bot(client):
    resp = client.get("/api/signals")
    assert resp.status_code == 200
    assert resp.json() == []
