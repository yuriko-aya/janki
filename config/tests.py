from django.test import TestCase, override_settings
from django.urls import reverse


class LegalPagesTestCase(TestCase):
    _test_storages = {
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    }

    @override_settings(STORAGES=_test_storages)
    def test_privacy_policy_page_loads(self):
        response = self.client.get(reverse('privacy_policy'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Privacy Policy')

    @override_settings(STORAGES=_test_storages)
    def test_terms_of_service_page_loads(self):
        response = self.client.get(reverse('terms_of_service'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Terms of Service')

    @override_settings(STORAGES=_test_storages)
    def test_footer_links_to_legal_pages(self):
        response = self.client.get(reverse('teams:team_list'))
        self.assertContains(response, reverse('privacy_policy'))
        self.assertContains(response, reverse('terms_of_service'))


class HomePageTestCase(TestCase):
    _test_storages = {
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    }

    @override_settings(STORAGES=_test_storages)
    def test_home_page_loads(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Janki Mahjong Score Tracker')

    @override_settings(STORAGES=_test_storages)
    def test_home_page_describes_app_purpose(self):
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'tracking Japanese Mahjong scores')
        self.assertContains(response, 'Uma')

    @override_settings(
        STORAGES=_test_storages,
        GOOGLE_SITE_VERIFICATION='test-verification-token',
    )
    def test_google_site_verification_meta_tag(self):
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'name="google-site-verification"')
        self.assertContains(response, 'content="test-verification-token"')


class SitemapTestCase(TestCase):
    _test_storages = {
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    }

    @classmethod
    def setUpTestData(cls):
        from teams.models import Team
        cls.public_team = Team.objects.create(name='Public Team', slug='public-team', hidden=False)
        cls.hidden_team = Team.objects.create(name='Hidden Team', slug='hidden-team', hidden=True)

    @override_settings(STORAGES=_test_storages)
    def test_sitemap_is_valid_xml(self):
        response = self.client.get(reverse('sitemap'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/xml')

    @override_settings(STORAGES=_test_storages)
    def test_sitemap_includes_public_team_pages(self):
        response = self.client.get(reverse('sitemap'))
        self.assertContains(response, '/teams/public-team/')
        self.assertContains(response, '/scores/public-team/standings/')
        self.assertContains(response, '/scores/public-team/sessions/')

    @override_settings(STORAGES=_test_storages)
    def test_sitemap_excludes_hidden_teams(self):
        response = self.client.get(reverse('sitemap'))
        self.assertNotContains(response, '/teams/hidden-team/')

    @override_settings(STORAGES=_test_storages, SITE_DOMAIN='janki.cc')
    def test_sitemap_uses_configured_domain(self):
        from django.contrib.sites.models import Site
        Site.objects.update_or_create(
            pk=1,
            defaults={'domain': 'janki.cc', 'name': 'Janki Mahjong Score Tracker'},
        )
        response = self.client.get(reverse('sitemap'))
        self.assertContains(response, 'https://janki.cc/teams/public-team/')
        self.assertNotContains(response, 'example.com')

    @override_settings(STORAGES=_test_storages)
    def test_sitemap_includes_static_pages(self):
        response = self.client.get(reverse('sitemap'))
        self.assertContains(response, reverse('home'))
        self.assertContains(response, reverse('privacy_policy'))

