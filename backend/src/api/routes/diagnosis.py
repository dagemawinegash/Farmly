import json

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from src.api.schemas.diagnosis import DiagnosisResponse
from src.auth.dependencies import get_current_user
from src.db.models.user import User, UserProfile
from src.db.session import get_db
from src.integrations.crop_health.kindwise_client import diagnose_with_kindwise
from src.integrations.llm.gemini_adapter import generate_reply


router = APIRouter(prefix="/api/crop-health", tags=["Crop Health"])


def _parse_lat_lon(location: str | None) -> tuple[float, float] | None:
    if not location:
        return None
    try:
        lat_str, lon_str = [x.strip() for x in location.split(",", maxsplit=1)]
        return float(lat_str), float(lon_str)
    except Exception:
        return None


def _fallback_advice(is_plant: bool, top_disease_name: str | None) -> str:
    if not is_plant:
        return "This image does not look like a crop plant. Please upload a clearer crop leaf photo."
    if top_disease_name:
        return (
            f"Possible issue detected: {top_disease_name}. "
            "Remove affected leaves, avoid overhead irrigation, and monitor spread over the next 3 to 5 days."
        )
    return (
        "No clear disease was detected from this image. "
        "Continue field monitoring and upload a closer leaf image if symptoms worsen."
    )


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

    coords = _parse_lat_lon(profile.location)
    lat, lon = coords if coords else (9.03, 38.74)

    try:
        diagnosis = diagnose_with_kindwise(image_bytes, latitude=lat, longitude=lon)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Diagnosis provider request failed: {exc}")

    crops = diagnosis.get("crops", [])
    diseases = diagnosis.get("diseases", [])
    is_plant = bool(diagnosis.get("is_plant", False))
    top_crop = crops[0] if crops else None
    top_disease = diseases[0] if diseases else None
    top_disease_name = top_disease.get("name") if top_disease else None

    if not is_plant:
        return DiagnosisResponse(
            is_plant=False,
            top_crop=None,
            top_disease=None,
            crops=[],
            diseases=[],
            advice_text="The uploaded image does not appear to be a plant. Please upload a clear crop leaf image.",
            used_fallback=False,
        )

    profile_context = {
        "location": profile.location or "",
        "preferred_language": profile.preferred_language or "",
        "crops_grown": profile.crops_grown or "",
        "diagnosis_summary": json.dumps(
            {
                "is_plant": is_plant,
                "top_crop": top_crop,
                "top_disease": top_disease,
            },
            ensure_ascii=False,
        ),
    }

    used_fallback = False
    try:
        advice_text = generate_reply(
            latest_user_message=(
                "Provide short farmer-friendly diagnosis advice based on this crop health result. "
                "Include what to do now and one prevention tip."
            ),
            recent_messages=[],
            profile_context=profile_context,
        )
    except Exception:
        used_fallback = True
        advice_text = _fallback_advice(is_plant, top_disease_name)

    return DiagnosisResponse(
        is_plant=is_plant,
        top_crop=top_crop,
        top_disease=top_disease,
        crops=crops,
        diseases=diseases,
        advice_text=advice_text,
        used_fallback=used_fallback,
    )
