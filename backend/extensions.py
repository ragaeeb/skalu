"""Flask extensions shared across the backend package."""
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="memory://",
    default_limits=["200 per day", "30 per hour"],
)
