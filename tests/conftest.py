import os
import tempfile

import pytest

from app import app as flask_app
from models import db as _db, User


@pytest.fixture()
def app():
    """Create a test app with a temporary database."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    flask_app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path}",
        "WTF_CSRF_ENABLED": False,  # disable CSRF for tests
        "SERVER_NAME": "localhost",
    })
    with flask_app.app_context():
        _db.create_all()
        yield flask_app
        _db.session.remove()
        _db.drop_all()
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def runner(app):
    return app.test_cli_runner()


@pytest.fixture()
def test_user(app):
    """Create and return a test user."""
    with app.app_context():
        user = User(username="testuser")
        user.set_password("testpassword123")
        _db.session.add(user)
        _db.session.commit()
        _db.session.refresh(user)
        return user
