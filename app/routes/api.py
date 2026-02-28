"""
API Router Aggregator.
Combines all route modules into a single API router.
"""
from fastapi import APIRouter
from app.routes import chat, admin, dashboard, whatsapp, health

# Create main API router
api_router = APIRouter()

# Include all sub-routers
api_router.include_router(health.router, tags=["health"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(whatsapp.router, prefix="/whatsapp", tags=["whatsapp"])
