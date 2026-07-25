from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

from accounts.models import EmailVerificationToken


class RegistrationTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.register_url = reverse('accounts:register')

    def test_registration_creates_inactive_user(self):
        """A new registration creates a user that cannot log in until verified."""
        response = self.client.post(self.register_url, {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': 'StrongPass123',
            'password_confirm': 'StrongPass123',
        })
        user = User.objects.get(username='newuser')
        self.assertFalse(user.is_active)

    def test_registration_creates_verification_token(self):
        """A verification token is created for the new user."""
        self.client.post(self.register_url, {
            'username': 'tokenuser',
            'email': 'tokenuser@example.com',
            'password': 'StrongPass123',
            'password_confirm': 'StrongPass123',
        })
        user = User.objects.get(username='tokenuser')
        self.assertTrue(EmailVerificationToken.objects.filter(user=user).exists())

    def test_registration_duplicate_username_rejected(self):
        """Registering with an existing username fails."""
        User.objects.create_user(username='existing', email='e@example.com', password='pass')
        response = self.client.post(self.register_url, {
            'username': 'existing',
            'email': 'new@example.com',
            'password': 'StrongPass123',
            'password_confirm': 'StrongPass123',
        })
        self.assertEqual(User.objects.filter(username='existing').count(), 1)


class EmailVerificationTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='verifyme',
            email='verify@example.com',
            password='pass',
            is_active=False
        )
        self.token = EmailVerificationToken.create_for_user(self.user)

    def test_valid_token_activates_user(self):
        """A valid token activates the user and deletes the token."""
        url = reverse('accounts:verify_email', kwargs={'token': self.token.token})
        self.client.get(url)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)
        self.assertFalse(EmailVerificationToken.objects.filter(user=self.user).exists())

    def test_valid_token_redirects_to_login(self):
        """Successful verification redirects to the login page."""
        url = reverse('accounts:verify_email', kwargs={'token': self.token.token})
        response = self.client.get(url)
        self.assertRedirects(response, reverse('accounts:login'))

    def test_invalid_token_returns_400(self):
        """An unknown token returns 400 Bad Request."""
        url = reverse('accounts:verify_email', kwargs={'token': 'not-a-real-token'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 400)

    def test_expired_token_does_not_activate_user(self):
        """An expired token redirects without activating the user."""
        self.token.created_at = timezone.now() - timedelta(days=8)
        self.token.save()
        url = reverse('accounts:verify_email', kwargs={'token': self.token.token})
        response = self.client.get(url)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertRedirects(response, reverse('accounts:register'))

    def test_token_is_deleted_after_use(self):
        """The token is consumed and cannot be reused."""
        url = reverse('accounts:verify_email', kwargs={'token': self.token.token})
        self.client.get(url)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 400)


class LoginTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.login_url = reverse('accounts:login')
        self.active_user = User.objects.create_user(
            username='active', email='active@example.com', password='pass', is_active=True
        )
        self.inactive_user = User.objects.create_user(
            username='inactive', email='inactive@example.com', password='pass', is_active=False
        )

    def test_active_user_can_login(self):
        """An active user with correct credentials is logged in."""
        response = self.client.post(self.login_url, {
            'username': 'active',
            'password': 'pass',
        })
        self.assertRedirects(response, reverse('teams:team_list'))
        self.assertIn('_auth_user_id', self.client.session)

    def test_inactive_user_cannot_login(self):
        """An unverified (inactive) user is rejected at login."""
        response = self.client.post(self.login_url, {
            'username': 'inactive',
            'password': 'pass',
        })
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_wrong_password_rejected(self):
        """Wrong credentials do not log the user in."""
        response = self.client.post(self.login_url, {
            'username': 'active',
            'password': 'wrongpass',
        })
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_logout_clears_session(self):
        """Logging out removes the user from the session."""
        self.client.login(username='active', password='pass')
        self.assertIn('_auth_user_id', self.client.session)
        self.client.get(reverse('accounts:logout'))
        self.assertNotIn('_auth_user_id', self.client.session)
