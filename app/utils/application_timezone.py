from datetime import timezone, datetime

APP_TIMEZONE = timezone.utc


def get_current_time() -> datetime:
    return datetime.now(APP_TIMEZONE)
