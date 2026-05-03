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
from src.services.advisory_service import (
    run_crop_recommendation,
    run_fertilizer_recommendation,
    run_weather_recommendation,
)


router = APIRouter(prefix="/api/recommendations", tags=["Recommendations"])


@router.post("/crops", response_model=RecommendationResponse, status_code=status.HTTP_200_OK)
def recommend_crops(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RecommendationResponse:
    profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.user_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found. Complete onboarding first.")
    result = run_crop_recommendation(profile)

    return RecommendationResponse(
        **result,
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
    result = run_fertilizer_recommendation(profile, payload.target_crop)

    return RecommendationResponse(
        **result,
    )


@router.post("/weather", response_model=WeatherRecommendationResponse, status_code=status.HTTP_200_OK)
def recommend_weather(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WeatherRecommendationResponse:
    profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.user_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found. Complete onboarding first.")
    try:
        result = run_weather_recommendation(profile)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Weather provider request failed: {exc}")

    return WeatherRecommendationResponse(
        **result,
    )
