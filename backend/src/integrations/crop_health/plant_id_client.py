import base64
from typing import Any

import httpx

from src.config.settings import get_settings


settings = get_settings()
PLANT_ID_IDENTIFICATION_URL = "https://api.plant.id/v3/identification"


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_common_names(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _simplify_plant_id_response(data: dict) -> dict:
    result = data.get("result") or {}
    is_plant_info = result.get("is_plant") or {}
    classification = result.get("classification") or {}

    crop_suggestions: list[dict] = []
    for suggestion in classification.get("suggestions") or []:
        details = suggestion.get("details") or {}
        scientific_name = suggestion.get("name")
        common_names = _normalize_common_names(details.get("common_names"))
        display_name = common_names[0] if common_names else scientific_name

        crop_suggestions.append(
            {
                "name": display_name,
                "scientific_name": scientific_name,
                "common_names": common_names,
                "probability": _as_float(suggestion.get("probability")),
                "similar_images": [],
            }
        )

    crop_suggestions.sort(key=lambda item: item.get("probability") or 0, reverse=True)

    return {
        "is_plant": bool(is_plant_info.get("binary")),
        "is_plant_probability": _as_float(is_plant_info.get("probability")),
        "crops": crop_suggestions,
    }


def identify_plant(image_bytes: bytes) -> dict:
    if not settings.kindwise_plant_id_api_key:
        raise RuntimeError("KINDWISE_PLANT_ID_API_KEY is not configured")

    encoded_image = base64.b64encode(image_bytes).decode("ascii")
    headers = {"Api-Key": settings.kindwise_plant_id_api_key}
    params = {"details": "common_names"}
    payload = {"images": [encoded_image]}

    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            PLANT_ID_IDENTIFICATION_URL,
            params=params,
            headers=headers,
            json=payload,
        )

    if response.status_code >= 400:
        raise RuntimeError(f"Plant.id provider error ({response.status_code}): {response.text}")

    data = response.json()
    if isinstance(data, dict) and data.get("error"):
        raise RuntimeError(f"Plant.id provider error: {data.get('error')}")

    return _simplify_plant_id_response(data)
