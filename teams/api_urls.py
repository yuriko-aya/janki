"""
API URL Configuration for Teams.
All endpoints require bearer token authentication except public endpoints.
"""
from django.urls import path
from teams.api_views import MemberCreateAPIView

app_name = 'teams_api'

urlpatterns = [
    # Member management endpoints
    path('teams/<slug:team_slug>/members/', 
         MemberCreateAPIView.as_view(), 
         name='member_create'),
]
