from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'

    def ready(self):
        from django.db.models.signals import post_migrate

        post_migrate.connect(self._sync_site, sender=self)

    @staticmethod
    def _sync_site(**kwargs):
        from accounts.site_sync import sync_site_domain

        sync_site_domain()
