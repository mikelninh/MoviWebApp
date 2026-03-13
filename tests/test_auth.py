"""Tests for authentication routes: register, login, logout, and security."""


def test_register_success(client):
    resp = client.post("/register", data={
        "name": "newuser", "password": "securepass123"
    }, follow_redirects=True)
    assert resp.status_code == 200


def test_register_short_password(client):
    resp = client.post("/register", data={
        "name": "newuser", "password": "short"
    }, follow_redirects=True)
    assert b"at least 8 characters" in resp.data


def test_register_missing_fields(client):
    resp = client.post("/register", data={
        "name": "", "password": ""
    }, follow_redirects=True)
    assert b"required" in resp.data


def test_register_duplicate_username(client, test_user):
    resp = client.post("/register", data={
        "name": "testuser", "password": "anotherpass123"
    }, follow_redirects=True)
    assert b"already taken" in resp.data


def test_login_success(client, test_user):
    resp = client.post("/login", data={
        "name": "testuser", "password": "testpassword123"
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b"Welcome back" in resp.data


def test_login_wrong_password(client, test_user):
    resp = client.post("/login", data={
        "name": "testuser", "password": "wrongpassword"
    }, follow_redirects=True)
    assert b"Invalid username or password" in resp.data


def test_login_nonexistent_user(client):
    resp = client.post("/login", data={
        "name": "noone", "password": "whatever123"
    }, follow_redirects=True)
    assert b"Invalid username or password" in resp.data


def test_login_open_redirect_blocked(client, test_user):
    """Ensure external URLs in ?next= are not followed (open redirect fix)."""
    resp = client.post("/login?next=https://evil.com", data={
        "name": "testuser", "password": "testpassword123"
    })
    assert resp.status_code == 302
    assert "evil.com" not in resp.headers.get("Location", "")


def test_login_safe_redirect(client, test_user):
    """Ensure safe internal redirects still work."""
    resp = client.post("/login?next=/feed", data={
        "name": "testuser", "password": "testpassword123"
    })
    assert resp.status_code == 302
    assert "/feed" in resp.headers.get("Location", "")


def test_logout(client, test_user):
    client.post("/login", data={
        "name": "testuser", "password": "testpassword123"
    })
    resp = client.get("/logout", follow_redirects=True)
    assert resp.status_code == 200
    assert b"logged out" in resp.data
