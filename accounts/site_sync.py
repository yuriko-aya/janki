from django.conf import settings
from django.contrib.sites.models import Site


def sync_site_domain():
    """Update Django Sites to match SITE_DOMAIN and APP_NAME settings."""
    Site.objects.update_or_create(
        pk=settings.SITE_ID,
        defaults={
            'domain': settings.SITE_DOMAIN,
            'name': settings.APP_NAME,
        },
    )
