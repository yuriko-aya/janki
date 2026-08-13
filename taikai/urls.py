from django.urls import path

from taikai import views

app_name = 'taikai'

urlpatterns = [
    path('', views.TournamentListView.as_view(), name='tournament_list'),
    path('create/', views.TournamentCreateView.as_view(), name='tournament_create'),
    path('admin/<int:pk>/remove/', views.RemoveTournamentAdminView.as_view(), name='admin_remove'),

    path('member/<int:pk>/edit/', views.TournamentMemberUpdateView.as_view(), name='member_update'),
    path('member/<int:pk>/delete/', views.TournamentMemberDeleteView.as_view(), name='member_delete'),

    path('<slug:slug>/', views.TournamentDetailView.as_view(), name='tournament_detail'),
    path('<slug:slug>/edit/', views.TournamentUpdateView.as_view(), name='tournament_update'),
    path('<slug:slug>/admins/', views.TournamentAdminListView.as_view(), name='admin_list'),
    path('<slug:slug>/admins/add/', views.AddTournamentAdminView.as_view(), name='admin_add'),
    path('<slug:slug>/member/<int:pk>/', views.TournamentMemberDetailView.as_view(), name='member_detail'),
    path('<slug:slug>/members/', views.TournamentMemberListView.as_view(), name='member_list'),
    path('<slug:slug>/members/add/', views.TournamentMemberCreateView.as_view(), name='member_create'),
    path('<slug:slug>/sessions/', views.TournamentSessionListView.as_view(), name='session_list'),
    path('<slug:slug>/sessions/create/', views.CreateManualSessionView.as_view(), name='session_create'),
    path('<slug:slug>/sessions/generate/', views.GenerateSessionsView.as_view(), name='generate_sessions'),
    path('<slug:slug>/sessions/generate-rank/', views.GenerateRankHanchanView.as_view(), name='generate_rank_hanchan'),
    path('<slug:slug>/sessions/<int:pk>/edit/', views.TournamentSessionEditView.as_view(), name='session_edit'),
]
