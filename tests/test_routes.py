"""Smoke tests for public and authenticated routes."""


def test_index(client):
    resp = client.get("/")
    assert resp.status_code == 200


def test_health_check(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json["status"] == "ok"


def test_about(client):
    resp = client.get("/about")
    assert resp.status_code == 200


def test_privacy(client):
    resp = client.get("/privacy")
    assert resp.status_code == 200


def test_browse(client):
    resp = client.get("/browse")
    assert resp.status_code == 200


def test_trending(client):
    resp = client.get("/trending")
    assert resp.status_code == 200


def test_movie_nights(client):
    resp = client.get("/movie-nights")
    assert resp.status_code == 200


def test_cinemas(client):
    resp = client.get("/cinemas")
    assert resp.status_code == 200


def test_lists_directory(client):
    resp = client.get("/lists")
    assert resp.status_code == 200


def test_404(client):
    resp = client.get("/nonexistent-page")
    assert resp.status_code == 404


def test_search_empty(client):
    resp = client.get("/search")
    assert resp.status_code == 200


def test_feed_requires_login(client):
    resp = client.get("/feed")
    assert resp.status_code == 302  # redirects to login


def test_settings_requires_login(client):
    resp = client.get("/settings")
    assert resp.status_code == 302


def _login(client, username="testuser", password="testpassword123"):
    return client.post("/login", data={
        "name": username, "password": password
    }, follow_redirects=True)


def test_feed_authenticated(client, test_user):
    _login(client)
    resp = client.get("/feed")
    assert resp.status_code == 200


def test_settings_authenticated(client, test_user):
    _login(client)
    resp = client.get("/settings")
    assert resp.status_code == 200


def test_challenges_authenticated(client, test_user):
    _login(client)
    resp = client.get("/challenges")
    assert resp.status_code == 200
