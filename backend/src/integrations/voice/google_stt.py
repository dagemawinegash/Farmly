from dataclasses import dataclass

from src.config.settings import get_settings
from src.integrations.voice.google_credentials import get_google_credentials


@dataclass(frozen=True)
class TranscriptionResult:
    transcript: str
    confidence: float | None
    language_code: str


def _load_speech_v2():
    from google.cloud import speech_v2

    return speech_v2


def transcribe_audio(audio_bytes: bytes) -> TranscriptionResult:
    settings = get_settings()
    if not settings.google_cloud_project:
        raise RuntimeError("GOOGLE_CLOUD_PROJECT is not configured.")

    speech_v2 = _load_speech_v2()
    client = speech_v2.SpeechClient(credentials=get_google_credentials())
    recognizer = (
        f"projects/{settings.google_cloud_project}/locations/"
        f"{settings.google_cloud_location}/recognizers/_"
    )
    config = speech_v2.RecognitionConfig(
        auto_decoding_config=speech_v2.AutoDetectDecodingConfig(),
        language_codes=[settings.google_stt_language_code],
        model=settings.google_stt_model,
    )
    request = speech_v2.RecognizeRequest(
        recognizer=recognizer,
        config=config,
        content=audio_bytes,
    )

    response = client.recognize(request=request)
    transcripts: list[str] = []
    confidences: list[float] = []

    for result in response.results:
        if not result.alternatives:
            continue
        alternative = result.alternatives[0]
        transcript = (alternative.transcript or "").strip()
        if transcript:
            transcripts.append(transcript)
        confidence = getattr(alternative, "confidence", None)
        if confidence is not None:
            confidences.append(float(confidence))

    transcript = " ".join(transcripts).strip()
    if not transcript:
        raise RuntimeError("Google Speech-to-Text returned no transcript.")

    return TranscriptionResult(
        transcript=transcript,
        confidence=max(confidences) if confidences else None,
        language_code=settings.google_stt_language_code,
    )
