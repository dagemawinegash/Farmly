from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

import httpx

from src.config.settings import get_settings
from src.services.language import is_amharic


HASAB_TRANSLATION_TARGET_ENGLISH = "eng"
HASAB_CHAT_TRANSLATION_MODEL = "hasab-1-lite"


@dataclass(frozen=True)
class HasabTranscriptionResult:
    transcript: str
    confidence: float | None
    language_code: str
    translation: str | None = None
    media_url: str | None = None


def _settings():
    return get_settings()


def _base_url() -> str:
    return _settings().hasab_api_base_url.rstrip("/")


def _headers() -> dict[str, str]:
    settings = _settings()
    if not settings.hasab_api_key:
        raise RuntimeError("HASAB_API_KEY is not configured.")
    return {
        "Authorization": f"Bearer {settings.hasab_api_key}",
        "Accept": "application/json",
    }


def _response_json(response: httpx.Response, operation: str) -> dict[str, Any]:
    try:
        data = response.json()
    except ValueError as exc:
        body = response.text.strip()
        if operation == "translation" and body:
            if body.startswith("data:"):
                for line in body.splitlines():
                    line = line.strip()
                    if line.startswith("data:"):
                        candidate = line.removeprefix("data:").strip()
                        if candidate and candidate != "[DONE]":
                            try:
                                data = httpx.Response(200, content=candidate).json()
                                if isinstance(data, dict):
                                    return data
                            except ValueError:
                                return {"content": candidate}
            return {"content": body}
        body_preview = body[:500] or "<empty response body>"
        raise RuntimeError(
            f"Hasab {operation} returned non-JSON response "
            f"({response.status_code}, {response.headers.get('content-type', 'unknown content-type')}): "
            f"{body_preview}"
        ) from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"Hasab {operation} returned unexpected JSON shape: {data!r}")
    return data


def _amharic_language_code(language_code: str | None) -> str:
    if not is_amharic(language_code):
        raise RuntimeError("Hasab voice integration is configured only for Amharic.")
    return _settings().hasab_amharic_language_code


def _extract_transcript(data: dict[str, Any]) -> str:
    candidates = [
        data.get("transcription"),
        (data.get("audio") or {}).get("transcription"),
        data.get("text"),
        data.get("transcript"),
        (data.get("data") or {}).get("transcription") if isinstance(data.get("data"), dict) else None,
    ]
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return ""


def _extract_media_url(data: dict[str, Any]) -> str | None:
    audio = data.get("audio") if isinstance(data.get("audio"), dict) else {}
    candidates = [
        data.get("audio_url"),
        audio.get("audio_url"),
        audio.get("url"),
        audio.get("path"),
    ]
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return None


def _extract_translation(data: dict[str, Any]) -> str | None:
    audio = data.get("audio") if isinstance(data.get("audio"), dict) else {}
    candidates = [
        data.get("translation"),
        audio.get("translation"),
        data.get("translated_text"),
        (data.get("data") or {}).get("translation") if isinstance(data.get("data"), dict) else None,
    ]
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return None


def _extract_chat_content(data: dict[str, Any]) -> str:
    message = data.get("message") if isinstance(data.get("message"), dict) else {}
    candidates = [
        message.get("content"),
        data.get("content"),
        data.get("text"),
        data.get("response"),
        (data.get("data") or {}).get("content") if isinstance(data.get("data"), dict) else None,
    ]
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return ""


def translate_text_with_hasab(
    text: str,
    *,
    source_language: str,
    target_language: str,
) -> str:
    if not text.strip():
        return ""

    source_is_amharic = is_amharic(source_language)
    target_is_amharic = is_amharic(target_language)
    if not (source_is_amharic or target_is_amharic):
        raise RuntimeError("Hasab translation is configured only for Amharic pairs.")

    source_name = "Amharic" if source_is_amharic else "English"
    target_name = "Amharic" if target_is_amharic else "English"
    prompt = (
        f"Translate the following {source_name} farming message into {target_name}. "
        "Return only the translation, with no explanation, labels, quotes, or markdown. "
        "Preserve crop names, disease names, fertilizer names, numbers, and units accurately.\n\n"
        f"{text.strip()}"
    )
    payload = {
        "message": prompt,
        "model": HASAB_CHAT_TRANSLATION_MODEL,
        "temperature": 0,
        "max_tokens": 1024,
        "stream": False,
    }

    settings = _settings()
    with httpx.Client(timeout=float(settings.hasab_timeout_seconds)) as client:
        response = client.post(
            f"{_base_url()}/v1/chat",
            headers={**_headers(), "Content-Type": "application/json"},
            json=payload,
        )

    if response.status_code >= 400:
        raise RuntimeError(f"Hasab translation error ({response.status_code}): {response.text}")

    translation = _extract_chat_content(_response_json(response, "translation"))
    if not translation:
        raise RuntimeError("Hasab translation returned no text.")
    return translation


def transcribe_with_hasab(
    audio_bytes: bytes,
    *,
    filename: str = "voice-message.webm",
    content_type: str = "audio/webm",
    language_code: str | None = None,
    translate_to_english: bool = False,
) -> HasabTranscriptionResult:
    settings = _settings()
    hasab_language = _amharic_language_code(language_code)
    url = f"{_base_url()}/v1/upload-audio"
    data = {
        "translate": "true" if translate_to_english else "false",
        "summarize": "false",
        "language": HASAB_TRANSLATION_TARGET_ENGLISH if translate_to_english else "auto",
        "transcribe": "true",
        "timestamps": "false",
        "source_language": hasab_language,
    }
    files = {
        "audio": (filename, audio_bytes, content_type),
    }

    with httpx.Client(timeout=float(settings.hasab_timeout_seconds)) as client:
        response = client.post(url, headers=_headers(), data=data, files=files)

    if response.status_code >= 400:
        raise RuntimeError(f"Hasab transcription error ({response.status_code}): {response.text}")

    payload = _response_json(response, "transcription")
    transcript = _extract_transcript(payload)
    if not transcript:
        raise RuntimeError("Hasab returned no transcript.")

    return HasabTranscriptionResult(
        transcript=transcript,
        confidence=None,
        language_code=hasab_language,
        translation=_extract_translation(payload),
        media_url=_extract_media_url(payload),
    )


def synthesize_with_hasab(text: str, *, language_code: str | None = None) -> bytes:
    settings = _settings()
    hasab_language = _amharic_language_code(language_code)
    url = f"{_base_url()}/v1/tts/synthesize"
    payload = {
        "text": text,
        "language": hasab_language,
        "speaker_name": settings.hasab_tts_amharic_speaker_name,
    }

    with httpx.Client(timeout=float(settings.hasab_timeout_seconds)) as client:
        response = client.post(url, headers={**_headers(), "Content-Type": "application/json"}, json=payload)

    if response.status_code >= 400:
        raise RuntimeError(f"Hasab TTS error ({response.status_code}): {response.text}")

    content_type = response.headers.get("content-type", "")
    if "application/json" not in content_type.lower():
        return bytes(response.content)

    data = response.json()
    audio_url = data.get("audio_url") or (data.get("record") or {}).get("audio_url")
    if not audio_url:
        raise RuntimeError("Hasab TTS returned JSON without audio content or audio_url.")

    with httpx.Client(timeout=float(settings.hasab_timeout_seconds)) as client:
        audio_response = client.get(urljoin(_base_url() + "/", audio_url))
    if audio_response.status_code >= 400:
        raise RuntimeError(
            f"Could not download Hasab TTS audio ({audio_response.status_code}): {audio_response.text}"
        )
    return bytes(audio_response.content)
