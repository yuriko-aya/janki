"""
API URL Configuration for Mahjong Score Tracker.
All API endpoints require bearer token authentication.
"""
from django.urls import path
from scores.api_views import (
    ValidateTokenAPIView,
    SessionSubmitAPIView,
    SessionUpdateAPIView,
    SessionDeleteAPIView
)

app_name = 'api'

urlpatterns = [
    # Token validation
    path('validate-token/', 
         ValidateTokenAPIView.as_view(), 
         name='validate_token'),
    
    # Session management endpoints
    path('teams/<slug:team_slug>/sessions/', 
         SessionSubmitAPIView.as_view(), 
         name='session_submit'),
    path('teams/<slug:team_slug>/sessions/<str:session_id>/', 
         SessionUpdateAPIView.as_view(), 
         name='session_update'),
    path('teams/<slug:team_slug>/sessions/<str:session_id>/delete/', 
         SessionDeleteAPIView.as_view(), 
         name='session_delete'),
]
