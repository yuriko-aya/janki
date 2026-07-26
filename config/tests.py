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
