def get_health_status() -> dict:
    """Business logic lives in services, not in routes.

    Later tasks can extend this (e.g. also check the database).
    """
    return {"status": "ok"}
