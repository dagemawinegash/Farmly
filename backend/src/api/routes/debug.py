from fastapi import APIRouter, Header, HTTPException, status
from sqlalchemy import delete

from src.config.settings import get_settings
from src.db.models.user import OTPVerification, PhoneChangeVerification, User, UserProfile
from src.db.session import SessionLocal


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

    db = SessionLocal()
    try:
        otp_deleted = db.execute(delete(OTPVerification)).rowcount or 0
        phone_change_deleted = db.execute(delete(PhoneChangeVerification)).rowcount or 0
        profile_deleted = db.execute(delete(UserProfile)).rowcount or 0
        user_deleted = db.execute(delete(User)).rowcount or 0
        db.commit()
    finally:
        db.close()

    return {
        "status": "success",
        "message": "All debug data removed",
        "deleted": {
            "users": user_deleted,
            "profiles": profile_deleted,
            "otp_verifications": otp_deleted,
            "phone_change_verifications": phone_change_deleted,
        },
    }
