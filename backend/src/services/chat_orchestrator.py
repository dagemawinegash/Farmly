from typing import Any, TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from src.db.models.chat import ChatMessage
from src.db.models.user import UserProfile
from src.integrations.llm.gemini_adapter import generate_reply
from src.services.advisory_service import (
    run_crop_recommendation,
    run_diagnosis,
    run_fertilizer_recommendation,
    run_weather_recommendation,
)


class OrchestratorState(TypedDict):
    message: str
    has_image: bool
    chosen_route: str
    result_text: str


def _build_profile_context(profile: UserProfile | None) -> dict[str, str]:
    if not profile:
        return {}
    return {
        "full_name": profile.full_name or "",
        "location": profile.location or "",
        "preferred_language": profile.preferred_language or "",
        "user_type": profile.user_type or "",
        "years_experience": str(profile.years_experience) if profile.years_experience is not None else "",
        "main_goal": profile.main_goal or "",
        "crops_grown": profile.crops_grown or "",
    }


def _collect_recent_messages(db: Session, session_id: str, limit: int = 5) -> list[dict[str, str]]:
    rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.sequence_no.desc())
        .limit(limit)
        .all()
    )
    rows = list(reversed(rows))
    return [{"sender": m.sender, "content": m.content} for m in rows]


def _classify_route(message: str, has_image: bool) -> str:
    if has_image:
        return "disease_diagnosis"
    text = (message or "").lower()
    if any(k in text for k in ["fertilizer", "fertiliser", "npk", "urea", "dap"]):
        return "fertilizer_recommendation"
    if any(k in text for k in ["weather", "rain", "forecast", "temperature", "wind"]):
        return "weather_recommendation"
    if any(k in text for k in ["recommend crop", "what crop", "what to plant", "which crop", "plant now"]):
        return "crop_recommendation"
    return "general"


def run_chat_orchestrator(
    *,
    db: Session,
    session_id: str,
    profile: UserProfile | None,
    message: str,
    image_bytes: bytes | None,
) -> tuple[str, str]:
    state: OrchestratorState = {
        "message": message,
        "has_image": bool(image_bytes),
        "chosen_route": "general",
        "result_text": "",
    }

    profile_context = _build_profile_context(profile)
    recent_messages = _collect_recent_messages(db, session_id, limit=5)
    def classify_node(s: OrchestratorState) -> OrchestratorState:
        s["chosen_route"] = _classify_route(s["message"], s["has_image"])
        return s

    def execute_node(s: OrchestratorState) -> OrchestratorState:
        route = s["chosen_route"]
        try:
            if route == "crop_recommendation":
                if not profile:
                    s["result_text"] = "Please complete onboarding profile first."
                else:
                    result = run_crop_recommendation(profile, recent_messages=recent_messages)
                    s["result_text"] = result["recommendation_text"]
            elif route == "fertilizer_recommendation":
                if not profile:
                    s["result_text"] = "Please complete onboarding profile first."
                else:
                    result = run_fertilizer_recommendation(profile, recent_messages=recent_messages)
                    s["result_text"] = result["recommendation_text"]
            elif route == "weather_recommendation":
                if not profile:
                    s["result_text"] = "Please complete onboarding profile first."
                else:
                    result = run_weather_recommendation(profile, recent_messages=recent_messages)
                    s["result_text"] = result["recommendation_text"]
            elif route == "disease_diagnosis":
                if not image_bytes:
                    s["result_text"] = "Please upload a plant image for diagnosis."
                elif not profile:
                    s["result_text"] = "Please complete onboarding profile first."
                else:
                    diagnosis = run_diagnosis(profile, image_bytes, recent_messages=recent_messages)
                    s["result_text"] = diagnosis.advice_text
            else:
                s["result_text"] = generate_reply(
                    latest_user_message=s["message"],
                    recent_messages=recent_messages,
                    profile_context=profile_context,
                )
        except Exception:
            fallback = s["message"].strip()[:120]
            s["result_text"] = (
                "I received your request and prepared a basic response.\n"
                f"Request: {fallback}\n"
                "Please try again if you want a more detailed advisory answer."
            )
        return s

    graph = StateGraph(OrchestratorState)
    graph.add_node("classify", classify_node)
    graph.add_node("execute", execute_node)
    graph.set_entry_point("classify")
    graph.add_edge("classify", "execute")
    graph.add_edge("execute", END)
    app = graph.compile()
    out: dict[str, Any] = app.invoke(state)
    return out["chosen_route"], out["result_text"]
