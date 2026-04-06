from fastapi import APIRouter

from app.api.v1 import posts

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(posts.router)

# Stubs — will be wired in future weeks
# api_router.include_router(videos.router)
# api_router.include_router(accounts.router)
# api_router.include_router(analytics.router)
# api_router.include_router(webhooks.router)
# api_router.include_router(api_keys.router)
