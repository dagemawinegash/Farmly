from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status

from src.api.schemas.voice import VoiceSynthesisRequest, VoiceTranscriptionResponse
from src.auth.dependencies import get_current_user
from src.config.settings import get_settings
from src.db.models.user import User
from src.integrations.voice.google_stt import transcribe_audio
from src.integrations.voice.google_tts import synthesize_speech


router = APIRouter(prefix="/api/voice", tags=["Voice"])


def _preferred_language(current_user: User, override: str | None = None) -> str | None:
    if override and override.strip():
        return override.strip()
    profile = getattr(current_user, "profile", None)
    return getattr(profile, "preferred_language", None)


async def _read_audio_upload(audio: UploadFile) -> bytes:
    content_type = (audio.content_type or "").lower()
    if not content_type.startswith("audio/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must be an audio file.",
        )

    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded audio is empty.",
        )

    settings = get_settings()
    if len(audio_bytes) > settings.voice_audio_max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Uploaded audio is too large.",
        )

    return audio_bytes


@router.post("/transcribe", response_model=VoiceTranscriptionResponse)
async def transcribe_voice(
    audio: UploadFile = File(...),
    language_code: str | None = Form(default=None),
    current_user: User = Depends(get_current_user),
) -> VoiceTranscriptionResponse:
    audio_bytes = await _read_audio_upload(audio)

    try:
        result = transcribe_audio(
            audio_bytes,
            language_code=_preferred_language(current_user, language_code),
            filename=audio.filename or "voice-message.webm",
            content_type=audio.content_type or "audio/webm",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Voice transcription failed: {exc}",
        ) from exc

    return VoiceTranscriptionResponse(
        transcript=result.transcript,
        confidence=result.confidence,
        language_code=result.language_code,
    )


@router.post("/synthesize", response_class=Response)
def synthesize_voice(
    payload: VoiceSynthesisRequest,
    current_user: User = Depends(get_current_user),
) -> Response:
    text = payload.text.strip()
    if not text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Text cannot be empty.",
        )

    try:
        audio_bytes = synthesize_speech(
            text,
            language_code=_preferred_language(current_user, payload.language_code),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Voice synthesis failed: {exc}",
        ) from exc

    return Response(content=audio_bytes, media_type="audio/mpeg")
