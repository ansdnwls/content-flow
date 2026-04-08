"""Viral Score Prediction API — predict content performance before publishing."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from app.api.deps import AuthenticatedUser, get_current_user
from app.api.error_responses import COMMON_RESPONSES
from app.services.viral_predictor import ViralPredictor

router = APIRouter(prefix="/predict", tags=["Prediction"], responses=COMMON_RESPONSES)
CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]


class ViralScoreRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "10 Python Tips You Didn't Know",
                "description": "Boost your Python skills with these hidden gems.",
                "platform": "youtube",
                "tags": ["python", "programming", "tips"],
                "thumbnail_url": "https://example.com/thumb.jpg",
            },
        },
    )

    title: str = Field(description="Content title")
    description: str = Field(description="Content description or body")
    platform: str = Field(description="Target platform (youtube, tiktok, instagram, x, linkedin)")
    tags: list[str] = Field(default_factory=list, description="Content tags/keywords")
    thumbnail_url: str | None = Field(default=None, description="Thumbnail image URL")


class ScoreBreakdownResponse(BaseModel):
    curiosity: int = Field(description="Title curiosity score (0-25)")
    keyword_trend: int = Field(description="Keyword trend matching score (0-25)")
    emotional_intensity: int = Field(description="Emotional engagement score (0-25)")
    platform_fit: int = Field(description="Platform format fitness score (0-25)")


class ViralScoreResponse(BaseModel):
    viral_score: int = Field(description="Overall viral score (0-100)")
    breakdown: ScoreBreakdownResponse
    suggestions: list[str] = Field(description="Improvement suggestions")
    ab_variants: list[dict] = Field(description="Alternative title+description combos")


class ABTestRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "10 Python Tips You Didn't Know",
                "description": "Boost your Python skills with these hidden gems.",
                "platform": "youtube",
                "tags": ["python", "programming"],
            },
        },
    )

    title: str = Field(description="Original title")
    description: str = Field(description="Original description")
    platform: str = Field(description="Target platform")
    tags: list[str] = Field(default_factory=list, description="Original tags")


class ABTestResponse(BaseModel):
    title_variants: list[str] = Field(description="3 title alternatives")
    description_variants: list[str] = Field(description="3 description alternatives")
    tag_variants: list[list[str]] = Field(description="3 tag set alternatives")


@router.post(
    "/viral-score",
    response_model=ViralScoreResponse,
    summary="Predict Viral Score",
    description=(
        "Analyze content before publishing and predict its viral potential. "
        "Returns a score 0-100 with breakdown, suggestions, and A/B variants."
    ),
)
async def predict_viral_score(
    req: ViralScoreRequest,
    user: CurrentUser,
) -> ViralScoreResponse:
    predictor = ViralPredictor()
    prediction = await predictor.predict_viral_score(
        title=req.title,
        description=req.description,
        platform=req.platform,
        tags=req.tags,
        thumbnail_url=req.thumbnail_url,
    )
    return ViralScoreResponse(
        viral_score=prediction.viral_score,
        breakdown=ScoreBreakdownResponse(
            curiosity=prediction.breakdown.curiosity,
            keyword_trend=prediction.breakdown.keyword_trend,
            emotional_intensity=prediction.breakdown.emotional_intensity,
            platform_fit=prediction.breakdown.platform_fit,
        ),
        suggestions=prediction.suggestions,
        ab_variants=prediction.ab_variants,
    )


@router.post(
    "/ab-test",
    response_model=ABTestResponse,
    summary="Generate A/B Test Variants",
    description=(
        "Automatically generate 3 variants each for title, description, and tags "
        "to enable A/B testing before publishing."
    ),
)
async def generate_ab_test(
    req: ABTestRequest,
    user: CurrentUser,
) -> ABTestResponse:
    predictor = ViralPredictor()
    result = await predictor.generate_ab_test(
        title=req.title,
        description=req.description,
        platform=req.platform,
        tags=req.tags,
    )
    return ABTestResponse(
        title_variants=result.title_variants,
        description_variants=result.description_variants,
        tag_variants=result.tag_variants,
    )
