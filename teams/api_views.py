"""
REST API views for team management.
Uses drf-multitokenauth bearer token authentication - supports multiple tokens per user.
"""
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from teams.models import Team, Member
from teams.api_serializers import MemberSerializer
from teams.services import resolve_player_for_new_member
from scores.authentication import BearerMultiTokenAuthentication


class MemberCreateAPIView(APIView):
    """
    POST /api/teams/<slug>/members/
    
    Create a new member in the team.
    Requires authentication and team admin permission.
    
    Request body:
    {
        "name": "Player Name"
    }
    
    Response (201 Created):
    {
        "success": true,
        "message": "Member 'Player Name' added to team successfully",
        "member": {
            "id": 1,
            "name": "Player Name",
            "join_date": "2025-12-31"
        }
    }
    
    Response (400 Bad Request) - validation error:
    {
        "success": false,
        "errors": {
            "name": ["Member 'Player Name' already exists in team Team Alpha"]
        }
    }
    
    Response (403 Forbidden) - not team admin:
    {
        "success": false,
        "message": "You do not have permission to add members to this team"
    }
    """
    authentication_classes = [BearerMultiTokenAuthentication]
    permission_classes = [IsAuthenticated]
    
    def post(self, request, team_slug):
        # Get the team
        team = get_object_or_404(Team, slug=team_slug)
        
        # Check if user is admin of this team
        if not team.is_admin(request.user):
            return Response({
                'success': False,
                'message': 'You do not have permission to add members to this team'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Validate the request data
        serializer = MemberSerializer(data=request.data, context={'team': team})
        if not serializer.is_valid():
            return Response({
                'success': False,
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        name = serializer.validated_data['name']
        confirm = serializer.validated_data.get('confirm_same_player')
        player, needs_confirmation, existing_teams = resolve_player_for_new_member(
            name, team, confirm_same_player=confirm
        )

        if needs_confirmation:
            teams_list = ', '.join(existing_teams)
            return Response({
                'success': False,
                'warning': 'duplicate_name',
                'message': (
                    f"This member already exists in these teams: {teams_list}. "
                    "Are you sure it's the same player?"
                ),
                'teams': existing_teams,
            }, status=status.HTTP_409_CONFLICT)

        # Create the member
        member = Member.objects.create(
            team=team,
            name=name,
            player=player,
        )
        
        return Response({
            'success': True,
            'message': f"Member '{member.name}' added to team successfully",
            'member': {
                'id': member.id,
                'name': member.name,
                'join_date': member.join_date.isoformat()
            }
        }, status=status.HTTP_201_CREATED)
