"""Flask extensions — instantiated here, initialized with the app in app.py."""

from flask_login import LoginManager
from flask_mail import Mail
from flask_wtf.csrf import CSRFProtect

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

csrf = CSRFProtect()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message_category = "error"
mail = Mail()
limiter = Limiter(get_remote_address, default_limits=[])
