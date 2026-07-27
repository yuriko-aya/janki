from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth.models import User
from django.core import mail
from django.utils import timezone
from datetime import timedelta

from accounts.models import EmailVerificationToken, PasswordResetToken
from teams.models import Team, Member, Player


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


class ContactTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.contact_url = reverse('accounts:contact')

    def test_contact_page_loads(self):
        response = self.client.get(self.contact_url)
        self.assertEqual(response.status_code, 200)

    def test_contact_form_sends_email(self):
        from unittest.mock import patch
        with patch('accounts.views.send_contact_email') as mock_send:
            response = self.client.post(self.contact_url, {
                'name': 'Test User',
                'email': 'test@example.com',
                'subject': 'Hello',
                'message': 'This is a test message.',
            })
            self.assertRedirects(response, self.contact_url)
            mock_send.assert_called_once_with(
                name='Test User',
                email='test@example.com',
                subject='Hello',
                message='This is a test message.',
            )

    def test_contact_form_requires_all_fields(self):
        response = self.client.post(self.contact_url, {
            'name': 'Test User',
            'email': '',
            'subject': 'Hello',
            'message': 'This is a test message.',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], 'email', 'This field is required.')


class SocialAccountAdapterTestCase(TestCase):
    def setUp(self):
        from accounts.adapters import SocialAccountAdapter
        self.adapter = SocialAccountAdapter()

    def test_save_user_activates_oauth_user(self):
        from unittest.mock import MagicMock, patch
        user = User.objects.create_user(
            username='oauthuser', email='oauth@example.com', password='x', is_active=False
        )
        sociallogin = MagicMock()
        sociallogin.user = user

        with patch(
            'accounts.adapters.DefaultSocialAccountAdapter.save_user',
            return_value=user,
        ):
            result = self.adapter.save_user(None, sociallogin)

        result.refresh_from_db()
        self.assertTrue(result.is_active)

    def test_pre_social_login_activates_inactive_user(self):
        user = User.objects.create_user(
            username='inactive', email='inactive@example.com', password='x', is_active=False
        )
        EmailVerificationToken.create_for_user(user)

        class FakeSocialLogin:
            pass

        sociallogin = FakeSocialLogin()
        sociallogin.user = user
        sociallogin._did_authenticate_by_email = 'inactive@example.com'

        self.adapter.pre_social_login(None, sociallogin)

        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertFalse(EmailVerificationToken.objects.filter(user=user).exists())

    def test_pre_social_login_preserves_password_for_verified_user(self):
        from allauth.socialaccount.internal.flows.email_authentication import wipe_password

        user = User.objects.create_user(
            username='alice', email='alice@example.com', password='goodpass', is_active=True
        )

        class FakeSocialLogin:
            pass

        sociallogin = FakeSocialLogin()
        sociallogin.user = user
        sociallogin._did_authenticate_by_email = 'alice@example.com'

        self.adapter.pre_social_login(None, sociallogin)
        wipe_password(None, user, 'alice@example.com')

        user.refresh_from_db()
        self.assertTrue(user.check_password('goodpass'))


class LoginWithEmailTestCase(TestCase):
    _test_storages = {
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    }

    def setUp(self):
        self.client = Client()
        self.login_url = reverse('accounts:login')
        self.user = User.objects.create_user(
            username='alice', email='alice@example.com', password='goodpass', is_active=True
        )

    @override_settings(STORAGES=_test_storages)
    def test_login_with_email_and_password(self):
        response = self.client.post(self.login_url, {
            'username': 'alice@example.com',
            'password': 'goodpass',
            'turnstile_token': 'test-token',
        })
        self.assertRedirects(response, reverse('teams:team_list'))
        self.assertIn('_auth_user_id', self.client.session)


class SocialLoginTemplateTestCase(TestCase):
    _test_storages = {
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    }

    @override_settings(
        STORAGES=_test_storages,
        SOCIALACCOUNT_PROVIDERS={
            'google': {
                'APP': {'client_id': 'test-google-id', 'secret': 'test-secret', 'key': ''},
            },
        },
    )
    def test_login_page_shows_google_button_when_configured(self):
        response = self.client.get(reverse('accounts:login'))
        self.assertContains(response, 'Continue with Google')

    @override_settings(STORAGES=_test_storages, SOCIALACCOUNT_PROVIDERS={})
    def test_login_page_hides_social_buttons_when_unconfigured(self):
        response = self.client.get(reverse('accounts:login'))
        self.assertNotContains(response, 'Continue with Google')


class ForgotPasswordTestCase(TestCase):
    _test_storages = {
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    }

    def setUp(self):
        self.client = Client()
        self.forgot_url = reverse('accounts:forgot_password')
        self.user = User.objects.create_user(
            username='alice', email='alice@example.com', password='oldpass', is_active=True
        )

    @override_settings(STORAGES=_test_storages)
    def test_forgot_password_shows_same_message_for_unknown_email(self):
        with self.settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'):
            response = self.client.post(self.forgot_url, {
                'email': 'missing@example.com',
                'turnstile_token': 'test-token',
            })
        self.assertRedirects(response, reverse('accounts:forgot_password_done'))
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(STORAGES=_test_storages)
    def test_forgot_password_sends_email_for_existing_user(self):
        from django.core import mail
        with self.settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'):
            response = self.client.post(self.forgot_url, {
                'email': 'alice@example.com',
                'turnstile_token': 'test-token',
            })
        self.assertRedirects(response, reverse('accounts:forgot_password_done'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('alice@example.com', mail.outbox[0].to)

    @override_settings(STORAGES=_test_storages)
    def test_reset_password_updates_password_and_invalidates_token(self):
        token = PasswordResetToken.create_for_user(self.user)
        reset_url = reverse('accounts:reset_password', kwargs={'token': token.token})

        response = self.client.post(reset_url, {
            'password': 'newpass123',
            'password_confirm': 'newpass123',
        })
        self.assertRedirects(response, reverse('accounts:login'))

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('newpass123'))
        self.assertFalse(PasswordResetToken.objects.filter(user=self.user).exists())

        follow_up = self.client.post(reset_url, {
            'password': 'anotherpass',
            'password_confirm': 'anotherpass',
        })
        self.assertRedirects(follow_up, reverse('accounts:forgot_password'))


class ProfileViewTestCase(TestCase):
    _test_storages = {
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    }

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='alice', password='pass')
        self.team = Team.objects.create(name='Team A', slug='team-a')
        self.player = Player.objects.create(name='Alice')
        Member.objects.create(team=self.team, name='Alice', player=self.player)

    @override_settings(STORAGES=_test_storages)
    def test_profile_claim_player(self):
        self.client.login(username='alice', password='pass')
        response = self.client.post(reverse('accounts:profile'), {
            'action': 'claim',
            'player_id': self.player.pk,
        })
        self.assertRedirects(response, reverse('accounts:profile'))
        self.player.refresh_from_db()
        self.assertEqual(self.player.user, self.user)

    @override_settings(STORAGES=_test_storages)
    def test_profile_shows_linked_player(self):
        self.player.user = self.user
        self.player.save()
        self.client.login(username='alice', password='pass')
        response = self.client.get(reverse('accounts:profile'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Linked Player')
        self.assertContains(response, 'View All-Team Stats')


class SyncSiteCommandTestCase(TestCase):
    def test_sync_site_updates_domain(self):
        from django.core.management import call_command
        from django.contrib.sites.models import Site
        from django.conf import settings

        Site.objects.update_or_create(
            pk=settings.SITE_ID,
            defaults={'domain': 'example.com', 'name': 'Old Name'},
        )
        call_command('sync_site')
        site = Site.objects.get(pk=settings.SITE_ID)
        self.assertEqual(site.domain, settings.SITE_DOMAIN)
        self.assertEqual(site.name, settings.APP_NAME)

