import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.api.schemas.recommendation import (
    FertilizerRecommendationRequest,
    RecommendationResponse,
    WeatherRecommendationResponse,
)
from src.auth.dependencies import get_current_user
from src.db.models.user import User, UserProfile
from src.db.session import get_db
from src.integrations.llm.gemini_adapter import generate_reply
from src.integrations.soil.isda_client import get_soil_summary
from src.integrations.weather.open_meteo import get_current_and_forecast, get_weather_summary


router = APIRouter(prefix="/api/recommendations", tags=["Recommendations"])


def _split_crops(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_lat_lon(location: str | None) -> tuple[float, float] | None:
    if not location:
        return None
    try:
        lat_str, lon_str = [x.strip() for x in location.split(",", maxsplit=1)]
        return float(lat_str), float(lon_str)
    except Exception:
        return None


def _fallback_text(kind: str, crops: list[str]) -> str:
    crops_text = ", ".join(crops) if crops else "your local crops"
    if kind == "crops":
        return (
            f"For {crops_text}, start with crops that match current season rainfall and soil.\n"
            "Use quality seeds, prepare land early, and plant on time.\n"
            "Keep spacing correct and remove weeds in the first 4 weeks."
        )
    return (
        f"For {crops_text}, apply fertilizer based on soil status and crop growth stage.\n"
        "Use basal fertilizer at planting and top-dress nitrogen at vegetative stage.\n"
        "Avoid over-application and apply before expected light rainfall."
    )


def _fallback_weather_text() -> str:
    return (
        "Check the next 5 days before planning farm work.\n"
        "Do fertilizer application before light rain, not heavy rain.\n"
        "Prepare drainage if rainfall is expected, and avoid spraying during strong wind."
    )


def _collect_context(profile: UserProfile) -> tuple[str | None, list[str], dict | None, dict | None]:
    location_used = profile.location
    crops_used = _split_crops(profile.crops_grown)
    lat_lon = _parse_lat_lon(location_used)

    soil_summary: dict | None = None
    weather_summary: dict | None = None
    if lat_lon:
        lat, lon = lat_lon
        try:
            soil_summary = get_soil_summary(lat, lon)
        except Exception:
            soil_summary = None
        try:
            weather_summary = get_weather_summary(lat, lon, past_days=7)
        except Exception:
            weather_summary = None

    return location_used, crops_used, soil_summary, weather_summary


def _build_profile_context(
    profile: UserProfile,
    location_used: str | None,
    crops_used: list[str],
    soil_summary: dict | None,
    weather_summary: dict | None,
) -> dict[str, str]:
    return {
        "full_name": profile.full_name or "",
        "location": location_used or "",
        "preferred_language": profile.preferred_language or "",
        "user_type": profile.user_type or "",
        "years_experience": str(profile.years_experience) if profile.years_experience is not None else "",
        "main_goal": profile.main_goal or "",
        "crops_grown": ", ".join(crops_used),
        "soil_summary": json.dumps(soil_summary, ensure_ascii=False) if soil_summary else "",
        "weather_summary": json.dumps(weather_summary, ensure_ascii=False) if weather_summary else "",
    }


@router.post("/crops", response_model=RecommendationResponse, status_code=status.HTTP_200_OK)
def recommend_crops(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RecommendationResponse:
    profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.user_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found. Complete onboarding first.")

    location_used, crops_used, soil_summary, weather_summary = _collect_context(profile)
    profile_context = _build_profile_context(
        profile, location_used, crops_used, soil_summary, weather_summary
    )
    prompt = (
        "Give crop recommendation for this farmer based on profile, soil, and weather context. "
        "Return short practical advice suitable for smallholder farmers."
    )

    used_fallback = False
    try:
        text = generate_reply(
            latest_user_message=prompt,
            recent_messages=[],
            profile_context=profile_context,
        )
    except Exception:
        used_fallback = True
        text = _fallback_text("crops", crops_used)

    return RecommendationResponse(
        recommendation_text=text,
        location_used=location_used,
        crops_used=crops_used,
        soil_summary=soil_summary,
        weather_summary=weather_summary,
        used_fallback=used_fallback,
    )


@router.post("/fertilizer", response_model=RecommendationResponse, status_code=status.HTTP_200_OK)
def recommend_fertilizer(
    payload: FertilizerRecommendationRequest = FertilizerRecommendationRequest(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RecommendationResponse:
    profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.user_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found. Complete onboarding first.")

    location_used, crops_used, soil_summary, weather_summary = _collect_context(profile)
    target_crop = payload.target_crop.strip() if payload and payload.target_crop else None
    if target_crop:
        crops_used = [target_crop]

    profile_context = _build_profile_context(
        profile, location_used, crops_used, soil_summary, weather_summary
    )
    prompt = (
        "Give fertilizer recommendation for this farmer based on profile, soil, weather, and target crop context. "
        "Return short practical advice with timing and simple dosage guidance."
    )

    used_fallback = False
    try:
        text = generate_reply(
            latest_user_message=prompt,
            recent_messages=[],
            profile_context=profile_context,
        )
    except Exception:
        used_fallback = True
        text = _fallback_text("fertilizer", crops_used)

    return RecommendationResponse(
        recommendation_text=text,
        location_used=location_used,
        crops_used=crops_used,
        soil_summary=soil_summary,
        weather_summary=weather_summary,
        used_fallback=used_fallback,
    )


@router.post("/weather", response_model=WeatherRecommendationResponse, status_code=status.HTTP_200_OK)
def recommend_weather(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WeatherRecommendationResponse:
    profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.user_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found. Complete onboarding first.")

    coords = _parse_lat_lon(profile.location)
    if not coords:
        raise HTTPException(
            status_code=400,
            detail="No valid coordinates found. Save location as 'lat,lon' in profile.",
        )
    lat, lon = coords
    location_used = profile.location or f"{lat},{lon}"

    try:
        raw_weather = get_current_and_forecast(lat, lon, forecast_days=5)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Weather provider request failed: {exc}")

    profile_context = {
        "full_name": profile.full_name or "",
        "location": location_used,
        "preferred_language": profile.preferred_language or "",
        "user_type": profile.user_type or "",
        "years_experience": str(profile.years_experience) if profile.years_experience is not None else "",
        "main_goal": profile.main_goal or "",
        "crops_grown": profile.crops_grown or "",
        "weather_summary": json.dumps(raw_weather, ensure_ascii=False),
    }

    prompt = (
        "Based on this 5-day weather forecast, give actionable farming advice for the next few days. "
        "Keep it simple and short for farmers, including warnings and what to do."
    )

    used_fallback = False
    try:
        recommendation_text = generate_reply(
            latest_user_message=prompt,
            recent_messages=[],
            profile_context=profile_context,
        )
    except Exception:
        used_fallback = True
        recommendation_text = _fallback_weather_text()

    return WeatherRecommendationResponse(
        recommendation_text=recommendation_text,
        location_used=location_used,
        raw_weather=raw_weather,
        used_fallback=used_fallback,
    )
