from django.conf import settings


def analytics(request):
    """Makes the Google Analytics ID available to every template as {{ ga_id }}."""
    return {"ga_id": getattr(settings, "GA_MEASUREMENT_ID", "")}
