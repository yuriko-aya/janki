from django.urls import path
from scores import views

app_name = 'scores'

urlpatterns = [
    # Public views
    path('<slug:slug>/standings/', views.StandingsView.as_view(), name='standings'),
    path('<slug:slug>/sessions/', views.SessionsView.as_view(), name='sessions'),
    
    # Admin views
    path('<slug:team_slug>/raw/', views.RawScoreListView.as_view(), name='rawscore_list'),
    path('<slug:team_slug>/submit/', views.SessionSubmitView.as_view(), name='session_submit'),
    path('<slug:team_slug>/edit/<str:session_id>/', views.SessionEditView.as_view(), name='session_edit'),
]
