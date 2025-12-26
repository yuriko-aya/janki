from django.urls import path
from teams import views

app_name = 'teams'

urlpatterns = [
    # Public views
    path('', views.TeamListView.as_view(), name='team_list'),
    
    # Admin views - Team management (must come before slug pattern to avoid conflict)
    path('create/', views.TeamCreateView.as_view(), name='team_create'),
    
    # Admin views - Member management (must come before slug pattern)
    path('member/<int:pk>/edit/', views.MemberUpdateView.as_view(), name='member_update'),
    path('member/<int:pk>/delete/', views.MemberDeleteView.as_view(), name='member_delete'),
    
    # Admin views - Team Admin management (must come before slug pattern)
    path('admin/<int:pk>/remove/', views.RemoveTeamAdminView.as_view(), name='admin_remove'),
    
    # Slug-based patterns (must come last)
    path('<slug:slug>/', views.TeamDetailView.as_view(), name='team_detail'),
    path('<slug:slug>/edit/', views.TeamUpdateView.as_view(), name='team_update'),
    path('<slug:slug>/members/', views.MemberListView.as_view(), name='member_list'),
    path('<slug:slug>/members/add/', views.MemberCreateView.as_view(), name='member_create'),
    path('<slug:slug>/admins/', views.TeamAdminListView.as_view(), name='admin_list'),
    path('<slug:slug>/admins/add/', views.AddTeamAdminView.as_view(), name='admin_add'),
]
