from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'

    def ready(self):
        from django.db.models.signals import post_migrate

        post_migrate.connect(self._sync_site, sender=self)
        try:
            self._sync_site(sender=self)
        except Exception:
            # Database may not be ready during initial setup.
            pass

    @staticmethod
    def _sync_site(**kwargs):
        from django.conf import settings
        from django.contrib.sites.models import Site

        Site.objects.update_or_create(
            pk=settings.SITE_ID,
            defaults={
                'domain': settings.SITE_DOMAIN,
                'name': settings.APP_NAME,
            },
        )
