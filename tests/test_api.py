"""Tests for the REST API v1 endpoints."""


def test_api_root(client):
    resp = client.get("/api/v1/")
    assert resp.status_code == 200
    data = resp.json
    assert data["name"] == "MoviWebApp API"
    assert "endpoints" in data


def test_api_films_empty(client):
    resp = client.get("/api/v1/films")
    assert resp.status_code == 200
    data = resp.json
    assert data["total"] == 0
    assert data["films"] == []


def test_api_film_not_found(client):
    resp = client.get("/api/v1/films/9999")
    assert resp.status_code == 404


def test_api_user_not_found(client):
    resp = client.get("/api/v1/users/nobody")
    assert resp.status_code == 404


def test_api_trending(client):
    resp = client.get("/api/v1/trending")
    assert resp.status_code == 200
    assert "trending" in resp.json
