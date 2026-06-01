from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from src.api.schemas.diagnosis import DiagnosisResponse
from src.auth.dependencies import get_current_user
from src.db.models.user import User, UserProfile
from src.db.session import get_db
from src.services.advisory_service import run_diagnosis


router = APIRouter(prefix="/api/crop-health", tags=["Crop Health"])


@router.post("/diagnose", response_model=DiagnosisResponse, status_code=status.HTTP_200_OK)
def diagnose_crop_health(
    image: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DiagnosisResponse:
    profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.user_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found. Complete onboarding first.")

    content_type = (image.content_type or "").lower()
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Uploaded file must be an image.")

    image_bytes = image.file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Uploaded image is empty.")

    try:
        return run_diagnosis(profile, image_bytes, image_mime_type=content_type)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Diagnosis provider request failed: {exc}")
