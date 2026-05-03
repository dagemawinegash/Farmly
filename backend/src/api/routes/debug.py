from fastapi import APIRouter, Header, HTTPException, status

from src.config.settings import get_settings
from src.db.base import Base
from src.db.session import engine
from src.db import models  # noqa: F401


router = APIRouter(prefix="/api/debug", tags=["Debug"])
settings = get_settings()


@router.post("/reset-all-data")
def reset_all_data(x_debug_token: str | None = Header(default=None)) -> dict:
    if not settings.debug:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Debug reset endpoint is disabled",
        )

    if not settings.debug_reset_token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="DEBUG_RESET_TOKEN is not configured",
        )

    if x_debug_token != settings.debug_reset_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid debug token",
        )

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    return {
        "status": "success",
        "message": "Database reset completed: all tables dropped and recreated",
    }
