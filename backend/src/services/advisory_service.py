import json

from src.api.schemas.diagnosis import DiagnosisResponse
from src.db.models.user import UserProfile
from src.integrations.crop_health.kindwise_client import diagnose_with_kindwise
from src.integrations.llm.gemini_adapter import generate_reply
from src.integrations.soil.isda_client import get_soil_summary
from src.integrations.weather.open_meteo import get_current_and_forecast, get_weather_summary


def split_crops(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_lat_lon(location: str | None) -> tuple[float, float] | None:
    if not location:
        return None
    try:
        lat_str, lon_str = [x.strip() for x in location.split(",", maxsplit=1)]
        return float(lat_str), float(lon_str)
    except Exception:
        return None


def build_profile_context(
    profile: UserProfile,
    location_used: str | None,
    crops_used: list[str],
    soil_summary: dict | None = None,
    weather_summary: dict | None = None,
    extra: dict[str, str] | None = None,
) -> dict[str, str]:
    data = {
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
    if extra:
        data.update(extra)
    return data


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


def _fallback_diagnosis_advice(is_plant: bool, top_disease_name: str | None) -> str:
    if not is_plant:
        return "The uploaded image does not appear to be a plant. Please upload a clear crop leaf image."
    if top_disease_name:
        return (
            f"Possible issue detected: {top_disease_name}. "
            "Remove affected leaves, avoid overhead irrigation, and monitor spread over the next 3 to 5 days."
        )
    return (
        "No clear disease was detected from this image. "
        "Continue field monitoring and upload a closer leaf image if symptoms worsen."
    )


def collect_soil_weather_context(profile: UserProfile) -> tuple[str | None, list[str], dict | None, dict | None]:
    location_used = profile.location
    crops_used = split_crops(profile.crops_grown)
    lat_lon = parse_lat_lon(location_used)

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


def run_crop_recommendation(profile: UserProfile, recent_messages: list[dict[str, str]] | None = None) -> dict:
    location_used, crops_used, soil_summary, weather_summary = collect_soil_weather_context(profile)
    profile_context = build_profile_context(profile, location_used, crops_used, soil_summary, weather_summary)

    used_fallback = False
    try:
        text = generate_reply(
            latest_user_message=(
                "Give crop recommendation for this farmer based on profile, soil, and weather context. "
                "Return short practical advice suitable for smallholder farmers."
            ),
            recent_messages=recent_messages or [],
            profile_context=profile_context,
        )
    except Exception:
        used_fallback = True
        text = _fallback_text("crops", crops_used)

    return {
        "recommendation_text": text,
        "location_used": location_used,
        "crops_used": crops_used,
        "soil_summary": soil_summary,
        "weather_summary": weather_summary,
        "used_fallback": used_fallback,
    }


def run_fertilizer_recommendation(
    profile: UserProfile,
    target_crop: str | None = None,
    recent_messages: list[dict[str, str]] | None = None,
) -> dict:
    location_used, crops_used, soil_summary, weather_summary = collect_soil_weather_context(profile)
    crop_override = target_crop.strip() if target_crop else ""
    if crop_override:
        crops_used = [crop_override]
    profile_context = build_profile_context(profile, location_used, crops_used, soil_summary, weather_summary)

    used_fallback = False
    try:
        text = generate_reply(
            latest_user_message=(
                "Give fertilizer recommendation for this farmer based on profile, soil, weather, and target crop context. "
                "Return short practical advice with timing and simple dosage guidance."
            ),
            recent_messages=recent_messages or [],
            profile_context=profile_context,
        )
    except Exception:
        used_fallback = True
        text = _fallback_text("fertilizer", crops_used)

    return {
        "recommendation_text": text,
        "location_used": location_used,
        "crops_used": crops_used,
        "soil_summary": soil_summary,
        "weather_summary": weather_summary,
        "used_fallback": used_fallback,
    }


def run_weather_recommendation(
    profile: UserProfile,
    recent_messages: list[dict[str, str]] | None = None,
) -> dict:
    coords = parse_lat_lon(profile.location)
    if not coords:
        raise ValueError("No valid coordinates found. Save location as 'lat,lon' in profile.")
    lat, lon = coords
    location_used = profile.location or f"{lat},{lon}"

    raw_weather = get_current_and_forecast(lat, lon, forecast_days=5)
    profile_context = build_profile_context(
        profile,
        location_used,
        split_crops(profile.crops_grown),
        weather_summary=raw_weather,
    )

    used_fallback = False
    try:
        recommendation_text = generate_reply(
            latest_user_message=(
                "Based on this 5-day weather forecast, give actionable farming advice for the next few days. "
                "Keep it simple and short for farmers, including warnings and what to do."
            ),
            recent_messages=recent_messages or [],
            profile_context=profile_context,
        )
    except Exception:
        used_fallback = True
        recommendation_text = _fallback_weather_text()

    return {
        "recommendation_text": recommendation_text,
        "location_used": location_used,
        "raw_weather": raw_weather,
        "used_fallback": used_fallback,
    }


def run_diagnosis(
    profile: UserProfile,
    image_bytes: bytes,
    recent_messages: list[dict[str, str]] | None = None,
) -> DiagnosisResponse:
    coords = parse_lat_lon(profile.location)
    lat, lon = coords if coords else (9.03, 38.74)
    diagnosis = diagnose_with_kindwise(image_bytes, latitude=lat, longitude=lon)

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
            advice_text=_fallback_diagnosis_advice(False, None),
            used_fallback=False,
        )

    profile_context = build_profile_context(
        profile,
        profile.location,
        split_crops(profile.crops_grown),
        extra={
            "diagnosis_summary": json.dumps(
                {"is_plant": is_plant, "top_crop": top_crop, "top_disease": top_disease},
                ensure_ascii=False,
            )
        },
    )

    used_fallback = False
    try:
        advice_text = generate_reply(
            latest_user_message=(
                "Provide short farmer-friendly diagnosis advice based on this crop health result. "
                "Include what to do now and one prevention tip."
            ),
            recent_messages=recent_messages or [],
            profile_context=profile_context,
        )
    except Exception:
        used_fallback = True
        advice_text = _fallback_diagnosis_advice(True, top_disease_name)

    return DiagnosisResponse(
        is_plant=is_plant,
        top_crop=top_crop,
        top_disease=top_disease,
        crops=crops,
        diseases=diseases,
        advice_text=advice_text,
        used_fallback=used_fallback,
    )

