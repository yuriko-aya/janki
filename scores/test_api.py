"""
Tests for REST API endpoints.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token
from datetime import date

from teams.models import Team, Member
from accounts.models import TeamAdmin
from scores.models import RawScore


class APITestCase(TestCase):
    """Test suite for REST API endpoints."""
    
    def setUp(self):
        """Set up test data."""
        # Create user
        self.user = User.objects.create_user(
            username='testadmin',
            password='testpass123',
            email='test@example.com'
        )
        
        # Create team
        self.team = Team.objects.create(
            name='Test Team',
            slug='test-team'
        )
        
        # Create team admin
        self.team_admin = TeamAdmin.objects.create(
            user=self.user,
            team=self.team
        )
        
        # Create members
        self.member1 = Member.objects.create(team=self.team, name='Player 1')
        self.member2 = Member.objects.create(team=self.team, name='Player 2')
        self.member3 = Member.objects.create(team=self.team, name='Player 3')
        self.member4 = Member.objects.create(team=self.team, name='Player 4')
        
        # Create API token
        self.token = Token.objects.create(user=self.user)
        
        # Set up API client
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
    
    def test_submit_session_success(self):
        """Test successful session submission via API."""
        payload = {
            'session_id': 'test-session-1',
            'session_date': '2024-12-23',
            'scores': [
                {'member_name': 'Player 1', 'score': 35000, 'chombo': False},
                {'member_name': 'Player 2', 'score': 30000, 'chombo': False},
                {'member_name': 'Player 3', 'score': 25000, 'chombo': False},
                {'member_name': 'Player 4', 'score': 10000, 'chombo': True},
            ]
        }
        
        response = self.client.post(
            f'/api/teams/{self.team.slug}/sessions/',
            payload,
            format='json'
        )
        
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['scores_created'], 4)
        
        # Verify scores were created
        scores = RawScore.objects.filter(session_id='test-session-1')
        self.assertEqual(scores.count(), 4)
    
    def test_submit_session_invalid_score_count(self):
        """Test submission with wrong number of scores."""
        payload = {
            'session_id': 'test-session-2',
            'scores': [
                {'member_name': 'Player 1', 'score': 35000, 'chombo': False},
                {'member_name': 'Player 2', 'score': 30000, 'chombo': False},
            ]
        }
        
        response = self.client.post(
            f'/api/teams/{self.team.slug}/sessions/',
            payload,
            format='json'
        )
        
        self.assertEqual(response.status_code, 400)
        self.assertIn('scores', response.data)
    
    def test_submit_session_duplicate(self):
        """Test submission of duplicate session."""
        # Create initial session
        RawScore.objects.create(
            member=self.member1,
            score=35000,
            session_id='existing-session'
        )
        
        payload = {
            'session_id': 'existing-session',
            'scores': [
                {'member_name': 'Player 1', 'score': 35000, 'chombo': False},
                {'member_name': 'Player 2', 'score': 30000, 'chombo': False},
                {'member_name': 'Player 3', 'score': 25000, 'chombo': False},
                {'member_name': 'Player 4', 'score': 10000, 'chombo': False},
            ]
        }
        
        response = self.client.post(
            f'/api/teams/{self.team.slug}/sessions/',
            payload,
            format='json'
        )
        
        self.assertEqual(response.status_code, 409)
        self.assertIn('error', response.data)
    
    def test_update_session_success(self):
        """Test successful session update via API."""
        # Create initial session
        RawScore.objects.create(member=self.member1, score=35000, session_id='update-test')
        RawScore.objects.create(member=self.member2, score=30000, session_id='update-test')
        RawScore.objects.create(member=self.member3, score=25000, session_id='update-test')
        RawScore.objects.create(member=self.member4, score=10000, session_id='update-test')
        
        payload = {
            'session_id': 'update-test',
            'scores': [
                {'member_name': 'Player 1', 'score': 36000, 'chombo': False},
                {'member_name': 'Player 2', 'score': 29000, 'chombo': False},
                {'member_name': 'Player 3', 'score': 26000, 'chombo': False},
                {'member_name': 'Player 4', 'score': 9000, 'chombo': True},
            ]
        }
        
        response = self.client.put(
            f'/api/teams/{self.team.slug}/sessions/update-test/',
            payload,
            format='json'
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['success'])
        
        # Verify scores were updated
        updated_score = RawScore.objects.get(member=self.member1, session_id='update-test')
        self.assertEqual(updated_score.score, 36000)
    
    def test_delete_session_success(self):
        """Test successful session deletion via API."""
        # Create session
        RawScore.objects.create(member=self.member1, score=35000, session_id='delete-test')
        RawScore.objects.create(member=self.member2, score=30000, session_id='delete-test')
        RawScore.objects.create(member=self.member3, score=25000, session_id='delete-test')
        RawScore.objects.create(member=self.member4, score=10000, session_id='delete-test')
        
        response = self.client.delete(
            f'/api/teams/{self.team.slug}/sessions/delete-test/delete/'
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['scores_deleted'], 4)
        
        # Verify scores were deleted
        scores = RawScore.objects.filter(session_id='delete-test')
        self.assertEqual(scores.count(), 0)
    
    def test_unauthorized_access(self):
        """Test API access without authentication."""
        client = APIClient()  # No credentials
        
        payload = {
            'session_id': 'test-session',
            'scores': []
        }
        
        response = client.post(
            f'/api/teams/{self.team.slug}/sessions/',
            payload,
            format='json'
        )
        
        self.assertEqual(response.status_code, 401)
    
    def test_wrong_team_access(self):
        """Test accessing another team's data."""
        # Create another team
        other_team = Team.objects.create(name='Other Team', slug='other-team')
        
        payload = {
            'session_id': 'test-session',
            'scores': [
                {'member_name': 'Player 1', 'score': 35000, 'chombo': False},
                {'member_name': 'Player 2', 'score': 30000, 'chombo': False},
                {'member_name': 'Player 3', 'score': 25000, 'chombo': False},
                {'member_name': 'Player 4', 'score': 10000, 'chombo': False},
            ]
        }
        
        response = self.client.post(
            f'/api/teams/{other_team.slug}/sessions/',
            payload,
            format='json'
        )
        
        self.assertEqual(response.status_code, 403)
