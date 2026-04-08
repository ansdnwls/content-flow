"""Admin API for managing feature flags."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.api.error_responses import COMMON_RESPONSES
from app.core.admin_auth import get_admin_user
from app.core.feature_flags import (
    FeatureFlag,
    FeatureFlagNameConflictError,
    FeatureFlagNotFoundError,
    FeatureFlagStorageError,
    FeatureFlagStore,
    FeatureFlagType,
    PlanName,
)

router = APIRouter(
    prefix="/feature-flags",
    tags=["Admin"],
    responses=COMMON_RESPONSES,
)

AdminUser = Annotated[dict, Depends(get_admin_user)]


def get_feature_flag_store_from_request(request: Request) -> FeatureFlagStore:
    redis = getattr(getattr(request.app, "state", None), "redis", None)
    return FeatureFlagStore(redis=redis)


FeatureFlagStoreDep = Annotated[
    FeatureFlagStore,
    Depends(get_feature_flag_store_from_request),
]


class FeatureFlagListResponse(BaseModel):
    data: list[FeatureFlag]
    total: int


class FeatureFlagCreateRequest(BaseModel):
    name: str = Field(..., pattern=r"^[a-z][a-z0-9_]{1,62}$")
    type: FeatureFlagType
    enabled: bool = True
    default_enabled: bool = False
    description: str | None = None
    percentage: int | None = Field(default=None, ge=0, le=100)
    user_ids: list[str] = Field(default_factory=list)
    required_plan: PlanName | None = None

    def to_feature_flag(self) -> FeatureFlag:
        return FeatureFlag.model_validate(self.model_dump())


class FeatureFlagUpdateRequest(BaseModel):
    enabled: bool | None = None
    default_enabled: bool | None = None
    description: str | None = None
    percentage: int | None = Field(default=None, ge=0, le=100)
    user_ids: list[str] | None = None
    required_plan: PlanName | None = None


class FeatureFlagEvaluateRequest(BaseModel):
    user_id: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)


class FeatureFlagEvaluateResponse(BaseModel):
    name: str
    enabled: bool
    flag: FeatureFlag


@router.get("", response_model=FeatureFlagListResponse, summary="List Feature Flags")
async def list_feature_flags(
    admin: AdminUser,
    store: FeatureFlagStoreDep,
) -> FeatureFlagListResponse:
    flags = await store.list_flags()
    return FeatureFlagListResponse(data=flags, total=len(flags))


@router.post(
    "",
    response_model=FeatureFlag,
    status_code=status.HTTP_201_CREATED,
    summary="Create Feature Flag",
)
async def create_feature_flag(
    payload: FeatureFlagCreateRequest,
    admin: AdminUser,
    store: FeatureFlagStoreDep,
) -> FeatureFlag:
    try:
        return await store.create_flag(payload.to_feature_flag())
    except FeatureFlagNameConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Feature flag '{exc.args[0]}' already exists",
        ) from exc
    except FeatureFlagStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Feature flag storage unavailable for '{exc.args[0]}'",
        ) from exc


@router.patch("/{name}", response_model=FeatureFlag, summary="Update Feature Flag")
async def update_feature_flag(
    name: str,
    payload: FeatureFlagUpdateRequest,
    admin: AdminUser,
    store: FeatureFlagStoreDep,
) -> FeatureFlag:
    try:
        return await store.update_flag(name, payload.model_dump(exclude_unset=True))
    except FeatureFlagNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Feature flag '{exc.args[0]}' not found",
        ) from exc
    except FeatureFlagStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Feature flag storage unavailable for '{exc.args[0]}'",
        ) from exc


@router.delete("/{name}", response_model=FeatureFlag | None, summary="Delete Feature Flag")
async def delete_feature_flag(
    name: str,
    admin: AdminUser,
    store: FeatureFlagStoreDep,
) -> FeatureFlag | None:
    try:
        return await store.delete_flag(name)
    except FeatureFlagNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Feature flag '{exc.args[0]}' not found",
        ) from exc
    except FeatureFlagStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Feature flag storage unavailable for '{exc.args[0]}'",
        ) from exc


@router.post(
    "/{name}/evaluate",
    response_model=FeatureFlagEvaluateResponse,
    summary="Evaluate Feature Flag",
)
async def evaluate_feature_flag(
    name: str,
    payload: FeatureFlagEvaluateRequest,
    admin: AdminUser,
    store: FeatureFlagStoreDep,
) -> FeatureFlagEvaluateResponse:
    flag = await store.get_flag(name)
    if flag is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Feature flag '{name}' not found",
        )
    enabled = await store.is_enabled(name, user_id=payload.user_id, context=payload.context)
    return FeatureFlagEvaluateResponse(name=name, enabled=enabled, flag=flag)
