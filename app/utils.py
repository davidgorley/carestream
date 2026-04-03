"""Utility functions for timezone-aware datetime handling."""
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def get_tz_aware_now():
    """
    Get current datetime in the configured timezone.
    Reads timezone from database Settings table. Falls back to env variable,
    then defaults to UTC if not found.
    
    This DOES NOT use app context, so it reads directly from env as fallback.
    For proper database reads, use get_tz_aware_now_with_app() with app context.
    
    Returns:
        datetime: Timezone-aware datetime object
    """
    # Try to get from environment first (fallback during app initialization)
    tz_name = os.getenv('TZ', 'America/New_York')
    
    try:
        tz = ZoneInfo(tz_name)
        return datetime.now(tz=tz)
    except Exception as e:
        # If timezone is invalid, log and fall back to UTC
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Invalid timezone '{tz_name}': {e}. Falling back to UTC.")
        return datetime.now(tz=timezone.utc)


def get_tz_aware_now_with_app(app):
    """
    Get current datetime in the configured timezone.
    Reads timezone from database Settings table. Falls back to env variable.
    Must be called with app context available.
    
    Returns:
        datetime: Timezone-aware datetime object
    """
    try:
        from app.models.settings import Settings
        
        # Try to read from database
        tz_name = Settings.get('timezone', None)
        
        # Fallback to environment variable
        if not tz_name:
            tz_name = os.getenv('TZ', 'America/New_York')
        
        tz = ZoneInfo(tz_name)
        return datetime.now(tz=tz)
    except Exception as e:
        # If anything fails, fall back to simple get_tz_aware_now
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"Could not read timezone from database: {e}. Using env/default.")
        return get_tz_aware_now()
