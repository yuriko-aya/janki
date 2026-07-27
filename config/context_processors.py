from django.conf import settings


def site_settings(request):
    return {
        'APP_NAME': settings.APP_NAME,
        'GOOGLE_SITE_VERIFICATION': settings.GOOGLE_SITE_VERIFICATION,
    }
