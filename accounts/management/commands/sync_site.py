from django.core.management.base import BaseCommand

from accounts.site_sync import sync_site_domain


class Command(BaseCommand):
    help = 'Sync Django Sites domain and name from SITE_DOMAIN and APP_NAME settings.'

    def handle(self, *args, **options):
        sync_site_domain()
        self.stdout.write(self.style.SUCCESS('Site domain synced successfully.'))
