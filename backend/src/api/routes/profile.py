from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.api.schemas.profile import (
    OnboardingCompleteRequest,
    ProfileResponse,
    ProfileUpdateRequest,
)
from src.auth.dependencies import get_current_user
from src.db.models.user import User, UserProfile
from src.db.session import get_db


router = APIRouter(tags=["Onboarding"])


def _split_crops(value: str | None) -> list[str]:
    if not value:
        return []
    return [crop.strip() for crop in value.split(",") if crop.strip()]


def _join_crops(crops: list[str]) -> str:
    return ",".join(crops)


def _to_profile_response(profile: UserProfile) -> ProfileResponse:
    return ProfileResponse(
        user_id=profile.user_id,
        full_name=profile.full_name,
        phone_number=profile.phone_number,
        location=profile.location,
        preferred_language=profile.preferred_language,
        user_type=profile.user_type,
        years_experience=profile.years_experience,
        main_goal=profile.main_goal,
        crops_grown=_split_crops(profile.crops_grown),
        onboarding_completed=profile.onboarding_completed,
        onboarding_completed_at=profile.onboarding_completed_at,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


@router.post(
    "/api/onboarding/complete",
    response_model=ProfileResponse,
    status_code=status.HTTP_200_OK,
)
def complete_onboarding(
    payload: OnboardingCompleteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProfileResponse:
    profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.user_id).first()

    if not profile:
        profile = UserProfile(user_id=current_user.user_id)
        db.add(profile)

    profile.full_name = payload.full_name
    profile.phone_number = payload.phone_number
    profile.location = payload.location
    profile.preferred_language = payload.preferred_language
    profile.user_type = payload.user_type
    profile.years_experience = payload.years_experience
    profile.main_goal = payload.main_goal
    profile.crops_grown = _join_crops(payload.crops_grown)
    profile.onboarding_completed = True
    profile.onboarding_completed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(profile)
    return _to_profile_response(profile)


@router.get("/api/users/me/profile", response_model=ProfileResponse)
def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProfileResponse:
    profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.user_id).first()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found",
        )
    return _to_profile_response(profile)


@router.patch("/api/users/me/profile", response_model=ProfileResponse)
def update_my_profile(
    payload: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProfileResponse:
    profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.user_id).first()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found",
        )

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided for update",
        )

    if "phone_number" in updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone number cannot be updated from this endpoint. Use phone-change flow.",
        )

    if "crops_grown" in updates and updates["crops_grown"] is not None:
        updates["crops_grown"] = _join_crops(updates["crops_grown"])

    for field_name, field_value in updates.items():
        setattr(profile, field_name, field_value)

    db.commit()
    db.refresh(profile)
    return _to_profile_response(profile)
