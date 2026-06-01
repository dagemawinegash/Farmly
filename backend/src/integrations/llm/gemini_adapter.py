import base64
import json
import re

import httpx

from src.config.settings import get_settings


settings = get_settings()


def _build_system_instruction(profile_context: dict[str, str]) -> str:
    profile_lines = []
    for key, value in profile_context.items():
        if value:
            profile_lines.append(f"- {key}: {value}")

    profile_block = "\n".join(profile_lines) if profile_lines else "- profile: not provided"
    return (
        "You are Farmly, an agricultural assistant for Ethiopian smallholder farmers.\n"
        "Give practical, clear, and simple advice suitable for the farmer's context.\n"
        "Prefer agriculture-focused answers. If off-topic, gently redirect to farming help.\n"
        "Keep the answer short and easy to understand for non-technical farmers.\n"
        "Use 3 to 6 short lines and avoid complex words.\n\n"
        "Farmer profile context:\n"
        f"{profile_block}"
    )


def _build_contents(recent_messages: list[dict[str, str]], latest_user_message: str) -> list[dict]:
    contents: list[dict] = []
    for msg in recent_messages:
        role = "user" if msg.get("sender") == "user" else "model"
        text = (msg.get("content") or "").strip()
        if not text:
            continue
        contents.append({"role": role, "parts": [{"text": text}]})

    contents.append({"role": "user", "parts": [{"text": latest_user_message.strip()}]})
    return contents


def _extract_json_object(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            raise RuntimeError(f"Gemini returned non-JSON response: {text[:300]}")
        return json.loads(match.group(0))


def generate_reply(
    *,
    latest_user_message: str,
    recent_messages: list[dict[str, str]],
    profile_context: dict[str, str],
) -> str:
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured")
    if not settings.gemini_model:
        raise RuntimeError("GEMINI_MODEL is not configured")

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.gemini_model}:generateContent"
    )

    payload = {
        "system_instruction": {
            "parts": [{"text": _build_system_instruction(profile_context)}],
        },
        "contents": _build_contents(recent_messages, latest_user_message),
        "generationConfig": {
            "temperature": 0.4,
        },
    }

    with httpx.Client(timeout=float(settings.gemini_timeout_seconds)) as client:
        response = client.post(
            url,
            params={"key": settings.gemini_api_key},
            json=payload,
        )

    if response.status_code >= 400:
        raise RuntimeError(f"Gemini provider error ({response.status_code}): {response.text}")

    data = response.json()
    candidates = data.get("candidates") or []
    if not candidates:
        raise RuntimeError("Gemini returned no candidates")

    parts = ((candidates[0].get("content") or {}).get("parts")) or []
    text = "".join([(p.get("text") or "") for p in parts]).strip()
    if not text:
        raise RuntimeError("Gemini returned empty response")

    return text


def classify_crop_image(
    *,
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
    supported_crops: list[str],
) -> dict:
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured")
    if not settings.gemini_model:
        raise RuntimeError("GEMINI_MODEL is not configured")

    supported_crop_text = ", ".join(sorted(set(supported_crops)))
    prompt = (
        "You are Farmly's crop image triage system.\n"
        "Look at the uploaded image and decide if it is a plant/crop image.\n"
        "If it is a plant, identify the most likely crop.\n"
        "Use English crop names and scientific names when possible, even if the crop is known in another language.\n"
        "Sorghum must be routed to Farmly's local sorghum disease model.\n"
        "Non-sorghum crops can be routed to Kindwise Crop.health only if they match this supported crop list:\n"
        f"{supported_crop_text}\n\n"
        "Return ONLY valid JSON with this exact shape:\n"
        "{\n"
        '  "is_plant": true,\n'
        '  "crop_name": "maize",\n'
        '  "scientific_name": "Zea mays",\n'
        '  "common_names": ["corn", "maize"],\n'
        '  "confidence": 0.85,\n'
        '  "is_sorghum": false,\n'
        '  "is_kindwise_supported": true,\n'
        '  "supported_crop_match": "maize",\n'
        '  "decision": "kindwise_crop_health",\n'
        '  "reason": "short reason"\n'
        "}\n\n"
        "Rules:\n"
        '- decision must be one of: "not_plant", "uncertain", "sorghum_model", '
        '"kindwise_crop_health", "unsupported_crop".\n'
        "- confidence must be a number from 0 to 1.\n"
        "- If this is not clearly a plant/crop image, set is_plant=false and decision=not_plant.\n"
        "- If the image is too unclear to identify the crop, set decision=uncertain.\n"
        "- Do not diagnose disease here. Only classify/reroute the image."
    )

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.gemini_model}:generateContent"
    )
    encoded_image = base64.b64encode(image_bytes).decode("ascii")
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": encoded_image,
                        }
                    },
                ],
            }
        ],
        "generationConfig": {
            "temperature": 0.0,
        },
    }

    with httpx.Client(timeout=float(settings.gemini_timeout_seconds)) as client:
        response = client.post(
            url,
            params={"key": settings.gemini_api_key},
            json=payload,
        )

    if response.status_code >= 400:
        raise RuntimeError(f"Gemini vision provider error ({response.status_code}): {response.text}")

    data = response.json()
    candidates = data.get("candidates") or []
    if not candidates:
        raise RuntimeError("Gemini vision returned no candidates")

    parts = ((candidates[0].get("content") or {}).get("parts")) or []
    text = "".join([(p.get("text") or "") for p in parts]).strip()
    if not text:
        raise RuntimeError("Gemini vision returned empty response")

    parsed = _extract_json_object(text)
    if not isinstance(parsed, dict):
        raise RuntimeError("Gemini vision returned JSON that is not an object")
    return parsed
