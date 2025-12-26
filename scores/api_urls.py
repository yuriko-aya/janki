"""
API URL Configuration for Mahjong Score Tracker.
Most API endpoints require bearer token authentication.
Public endpoints: /teams/<slug>/exists/
"""
from django.urls import path
from scores.api_views import (
    TeamExistsAPIView,
    ValidateTokenAPIView,
    SessionSubmitAPIView,
    SessionUpdateAPIView,
    SessionDeleteAPIView
)

app_name = 'api'

urlpatterns = [
    # Public endpoints
    path('teams/<slug:team_slug>/exists/', 
         TeamExistsAPIView.as_view(), 
         name='team_exists'),
    
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
