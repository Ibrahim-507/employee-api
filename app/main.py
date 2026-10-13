from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import settings
from app.core.errors import register_exception_handlers

app = FastAPI(title=settings.app_name, version="0.3.0")
register_exception_handlers(app)
app.include_router(api_router)
