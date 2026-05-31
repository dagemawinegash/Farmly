import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.api.schemas.alert import (
    WeatherAlertDeleteResponse,
    WeatherAlertGenerateResponse,
    WeatherAlertReadResponse,
    WeatherAlertResponse,
)
from src.auth.dependencies import get_current_user
from src.db.models.alert import WeatherAlert
from src.db.models.user import User, UserProfile
from src.db.session import get_db
from src.services.alert_service import build_weather_alerts


router = APIRouter(prefix="/api/alerts", tags=["Alerts"])


def _decode_weather(raw_weather: str | None) -> dict | None:
    if not raw_weather:
        return None
    try:
        return json.loads(raw_weather)
    except json.JSONDecodeError:
        return None


def _to_response(alert: WeatherAlert) -> WeatherAlertResponse:
    return WeatherAlertResponse(
        alert_id=alert.alert_id,
        user_id=alert.user_id,
        alert_type=alert.alert_type,
        severity=alert.severity,
        title=alert.title,
        message=alert.message,
        action_text=alert.action_text,
        location_used=alert.location_used,
        raw_weather=_decode_weather(alert.raw_weather),
        is_read=alert.is_read,
        created_at=alert.created_at,
    )


@router.get("", response_model=list[WeatherAlertResponse])
def list_alerts(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[WeatherAlertResponse]:
    alerts = (
        db.query(WeatherAlert)
        .filter(WeatherAlert.user_id == current_user.user_id)
        .order_by(WeatherAlert.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [_to_response(alert) for alert in alerts]


@router.post(
    "/weather/generate",
    response_model=WeatherAlertGenerateResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_weather_alerts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WeatherAlertGenerateResponse:
    profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.user_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found. Complete onboarding first.")

    try:
        location_used, raw_weather, alert_payloads = build_weather_alerts(profile)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Weather alert provider request failed: {exc}")

    created_alerts: list[WeatherAlert] = []
    raw_weather_json = json.dumps(raw_weather, ensure_ascii=False)
    for payload in alert_payloads:
        alert = WeatherAlert(
            user_id=current_user.user_id,
            alert_type=payload["alert_type"],
            severity=payload["severity"],
            title=payload["title"],
            message=payload["message"],
            action_text=payload["action_text"],
            location_used=location_used,
            raw_weather=raw_weather_json,
        )
        db.add(alert)
        created_alerts.append(alert)

    db.commit()
    for alert in created_alerts:
        db.refresh(alert)

    return WeatherAlertGenerateResponse(
        generated_count=len(created_alerts),
        alerts=[_to_response(alert) for alert in created_alerts],
    )


@router.patch("/{alert_id}/read", response_model=WeatherAlertReadResponse)
def mark_alert_read(
    alert_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WeatherAlertReadResponse:
    alert = (
        db.query(WeatherAlert)
        .filter(
            WeatherAlert.alert_id == alert_id,
            WeatherAlert.user_id == current_user.user_id,
        )
        .first()
    )
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.is_read = True
    db.commit()
    db.refresh(alert)
    return WeatherAlertReadResponse(
        message="Alert marked as read",
        alert=_to_response(alert),
    )


@router.delete("/{alert_id}", response_model=WeatherAlertDeleteResponse)
def delete_alert(
    alert_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WeatherAlertDeleteResponse:
    alert = (
        db.query(WeatherAlert)
        .filter(
            WeatherAlert.alert_id == alert_id,
            WeatherAlert.user_id == current_user.user_id,
        )
        .first()
    )
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    deleted_id = alert.alert_id
    db.delete(alert)
    db.commit()
    return WeatherAlertDeleteResponse(
        message="Alert deleted successfully",
        alert_id=deleted_id,
    )
