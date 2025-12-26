"""
REST API views for score submission.
Uses drf-multitokenauth bearer token authentication - supports multiple tokens per user.
"""
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError as DjangoValidationError

from teams.models import Team, Member
from scores.models import RawScore
from scores.services.calculator import submit_session_scores, update_session_scores
from scores.api_serializers import SessionScoresSerializer
from scores.authentication import BearerMultiTokenAuthentication


class TeamExistsAPIView(APIView):
    """
    GET /api/teams/<slug>/exists/
    
    Public endpoint to check if a team exists.
    No authentication required.
    
    Response (200 OK) - if team exists:
    {
        "exists": true,
        "team": {
            "name": "Team Alpha",
            "slug": "team-alpha"
        }
    }
    
    Response (404 Not Found) - if team does not exist:
    {
        "exists": false,
        "message": "Team not found"
    }
    """
    authentication_classes = []  # No authentication required
    permission_classes = []  # Public endpoint
    
    def get(self, request, team_slug):
        try:
            team = Team.objects.get(slug=team_slug)
            return Response({
                'exists': True,
                'team': {
                    'name': team.name,
                    'slug': team.slug
                }
            }, status=status.HTTP_200_OK)
        except Team.DoesNotExist:
            return Response({
                'exists': False,
                'message': 'Team not found'
            }, status=status.HTTP_404_NOT_FOUND)


class ValidateTokenAPIView(APIView):
    """
    GET /api/validate-token/
    
    Validate that the provided bearer token is valid and active.
    Returns user information if token is valid.
    
    Response (200 OK):
    {
        "valid": true,
        "user": {
            "id": 1,
            "username": "admin",
            "email": "admin@example.com"
        },
        "teams": [
            {"id": 1, "name": "Team Alpha", "slug": "team-alpha"},
            {"id": 2, "name": "Team Beta", "slug": "team-beta"}
        ]
    }
    
    Response (401 Unauthorized) - if token is invalid:
    {
        "detail": "Invalid token."
    }
    """
    authentication_classes = [BearerMultiTokenAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        # Get all teams where user is admin
        from accounts.models import TeamAdmin
        team_admins = TeamAdmin.objects.filter(user=request.user).select_related('team')
        teams = [{
            'id': admin.team.id,
            'name': admin.team.name,
            'slug': admin.team.slug
        } for admin in team_admins]
        
        return Response({
            'valid': True,
            'user': {
                'id': request.user.id,
                'username': request.user.username,
                'email': request.user.email
            },
            'teams': teams
        }, status=status.HTTP_200_OK)


class SessionSubmitAPIView(APIView):
    """
    POST /api/teams/{team_slug}/sessions/
    
    Submit a new session with exactly 4 scores.
    Requires bearer token authentication.
    
    Request Body:
    {
        "session_id": "string",
        "session_date": "YYYY-MM-DD" (optional),
        "scores": [
            {"member_id": int, "score": int, "chombo": bool},
            {"member_id": int, "score": int, "chombo": bool},
            {"member_id": int, "score": int, "chombo": bool},
            {"member_id": int, "score": int, "chombo": bool}
        ]
    }
    
    Response:
    {
        "success": true,
        "message": "Session {session_id} scores submitted successfully",
        "session_id": "string",
        "scores_created": 4
    }
    """
    authentication_classes = [BearerMultiTokenAuthentication]
    permission_classes = [IsAuthenticated]
    
    def post(self, request, team_slug):
        # Get team
        team = get_object_or_404(Team, slug=team_slug)
        
        # Check if user is team admin
        if not team.admins.filter(user=request.user).exists():
            return Response(
                {'error': 'You do not have permission to submit scores for this team.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Validate request data
        serializer = SessionScoresSerializer(data=request.data, context={'team': team})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        # Extract validated data
        session_id = serializer.validated_data['session_id']
        session_date = serializer.validated_data.get('session_date')
        scores_data = serializer.validated_data['scores']
        
        # Convert member names to IDs
        from teams.models import Member
        converted_scores = []
        for score in scores_data:
            member = Member.objects.get(name=score['member_name'], team=team)
            converted_scores.append({
                'member_id': member.id,
                'score': score['score'],
                'chombo': score.get('chombo', 0)
            })
        
        # Check if session already exists
        existing_scores = RawScore.objects.filter(
            member__team=team,
            session_id=session_id
        )
        if existing_scores.exists():
            return Response(
                {
                    'error': f'Session {session_id} already exists. Use PUT to update.',
                    'existing_scores': existing_scores.count()
                },
                status=status.HTTP_409_CONFLICT
            )
        
        # Submit session scores
        try:
            created_scores = submit_session_scores(
                session_id=session_id,
                team=team,
                score_data=converted_scores,
                session_date=session_date
            )
            
            return Response(
                {
                    'success': True,
                    'message': f'Session {session_id} scores submitted successfully',
                    'session_id': session_id,
                    'scores_created': len(created_scores)
                },
                status=status.HTTP_201_CREATED
            )
        except (DjangoValidationError, Exception) as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class SessionUpdateAPIView(APIView):
    """
    PUT /api/teams/{team_slug}/sessions/{session_id}/
    
    Update an existing session with exactly 4 scores.
    Requires bearer token authentication.
    
    Request Body: Same as SessionSubmitAPIView
    
    Response:
    {
        "success": true,
        "message": "Session {session_id} updated successfully",
        "session_id": "string",
        "scores_updated": 4
    }
    """
    authentication_classes = [BearerMultiTokenAuthentication]
    permission_classes = [IsAuthenticated]
    
    def put(self, request, team_slug, session_id):
        # Get team
        team = get_object_or_404(Team, slug=team_slug)
        
        # Check if user is team admin
        if not team.admins.filter(user=request.user).exists():
            return Response(
                {'error': 'You do not have permission to update scores for this team.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if session exists
        existing_scores = RawScore.objects.filter(
            member__team=team,
            session_id=session_id
        )
        if not existing_scores.exists():
            return Response(
                {
                    'error': f'Session {session_id} does not exist. Use POST to create.',
                },
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Validate request data
        serializer = SessionScoresSerializer(data=request.data, context={'team': team})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        # Extract validated data
        session_date = serializer.validated_data.get('session_date')
        scores_data = serializer.validated_data['scores']
        
        # Convert member names to IDs
        from teams.models import Member
        converted_scores = []
        for score in scores_data:
            member = Member.objects.get(name=score['member_name'], team=team)
            converted_scores.append({
                'member_id': member.id,
                'score': score['score'],
                'chombo': score.get('chombo', 0)
            })
        
        # Update session scores
        try:
            updated_scores = update_session_scores(
                session_id=session_id,
                team=team,
                score_data=converted_scores,
                session_date=session_date
            )
            
            return Response(
                {
                    'success': True,
                    'message': f'Session {session_id} updated successfully',
                    'session_id': session_id,
                    'scores_updated': len(updated_scores)
                },
                status=status.HTTP_200_OK
            )
        except (DjangoValidationError, Exception) as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class SessionDeleteAPIView(APIView):
    """
    DELETE /api/teams/{team_slug}/sessions/{session_id}/
    
    Delete an existing session and all its scores.
    Requires bearer token authentication.
    
    Response:
    {
        "success": true,
        "message": "Session {session_id} deleted successfully",
        "scores_deleted": 4
    }
    """
    authentication_classes = [BearerMultiTokenAuthentication]
    permission_classes = [IsAuthenticated]
    
    def delete(self, request, team_slug, session_id):
        # Get team
        team = get_object_or_404(Team, slug=team_slug)
        
        # Check if user is team admin
        if not team.admins.filter(user=request.user).exists():
            return Response(
                {'error': 'You do not have permission to delete scores for this team.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get session scores
        session_scores = RawScore.objects.filter(
            member__team=team,
            session_id=session_id
        )
        
        if not session_scores.exists():
            return Response(
                {'error': f'Session {session_id} does not exist.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Delete scores and recalculate affected members
        affected_members = set(score.member for score in session_scores)
        count = session_scores.count()
        session_scores.delete()
        
        # Recalculate all affected members
        from scores.services.calculator import recalculate_member_score
        for member in affected_members:
            recalculate_member_score(member)
        
        return Response(
            {
                'success': True,
                'message': f'Session {session_id} deleted successfully',
                'scores_deleted': count
            },
            status=status.HTTP_200_OK
        )
