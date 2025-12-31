"""
Tests for Teams REST API endpoints.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from drf_multitokenauth.models import MultiToken

from teams.models import Team, Member
from accounts.models import TeamAdmin


class MemberCreateAPITestCase(TestCase):
    """Test cases for POST /api/teams/<slug>/members/ endpoint."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create users
        self.admin_user = User.objects.create_user(
            username='admin@test.com',
            email='admin@test.com',
            password='testpass123'
        )
        self.other_user = User.objects.create_user(
            username='other@test.com',
            email='other@test.com',
            password='testpass123'
        )
        
        # Create team
        self.team = Team.objects.create(
            name='Test Team',
            slug='test-team'
        )
        
        # Create team admin
        self.team_admin = TeamAdmin.objects.create(
            user=self.admin_user,
            team=self.team
        )
        
        # Create API client
        self.client = APIClient()
        
        # Create auth token for admin user
        self.admin_token = MultiToken.objects.create(user=self.admin_user)
        
        # Create auth token for other user
        self.other_token = MultiToken.objects.create(user=self.other_user)
    
    def test_create_member_success(self):
        """Test successfully creating a new member."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token.key}')
        
        response = self.client.post(
            f'/api/teams/{self.team.slug}/members/',
            {'name': 'New Player'},
            format='json'
        )
        
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['member']['name'], 'New Player')
        
        # Verify member was created in database
        member = Member.objects.get(team=self.team, name='New Player')
        self.assertIsNotNone(member)
    
    def test_create_member_duplicate_name(self):
        """Test creating a member with duplicate name fails."""
        # Create existing member
        Member.objects.create(team=self.team, name='Existing Player')
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token.key}')
        
        response = self.client.post(
            f'/api/teams/{self.team.slug}/members/',
            {'name': 'Existing Player'},
            format='json'
        )
        
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data['success'])
        self.assertIn('name', response.data['errors'])
    
    def test_create_member_empty_name(self):
        """Test creating a member with empty name fails."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token.key}')
        
        response = self.client.post(
            f'/api/teams/{self.team.slug}/members/',
            {'name': '   '},
            format='json'
        )
        
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data['success'])
    
    def test_create_member_no_auth(self):
        """Test creating a member without authentication fails."""
        response = self.client.post(
            f'/api/teams/{self.team.slug}/members/',
            {'name': 'New Player'},
            format='json'
        )
        
        self.assertEqual(response.status_code, 401)
    
    def test_create_member_wrong_team_admin(self):
        """Test creating a member as non-admin of the team fails."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.other_token.key}')
        
        response = self.client.post(
            f'/api/teams/{self.team.slug}/members/',
            {'name': 'New Player'},
            format='json'
        )
        
        self.assertEqual(response.status_code, 403)
        self.assertFalse(response.data['success'])
        self.assertIn('permission', response.data['message'].lower())
    
    def test_create_member_team_not_found(self):
        """Test creating a member for non-existent team returns 404."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token.key}')
        
        response = self.client.post(
            '/api/teams/non-existent-team/members/',
            {'name': 'New Player'},
            format='json'
        )
        
        self.assertEqual(response.status_code, 404)
    
    def test_create_member_missing_name(self):
        """Test creating a member without name field fails."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token.key}')
        
        response = self.client.post(
            f'/api/teams/{self.team.slug}/members/',
            {},
            format='json'
        )
        
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data['success'])
        self.assertIn('name', response.data['errors'])
