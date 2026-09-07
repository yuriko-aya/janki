from django.conf import settings


def site_settings(request):
    return {
        'APP_NAME': settings.APP_NAME,
        'GOOGLE_SITE_VERIFICATION': settings.GOOGLE_SITE_VERIFICATION,
        'GA4_MEASUREMENT_ID': settings.GA4_MEASUREMENT_ID,
    }
