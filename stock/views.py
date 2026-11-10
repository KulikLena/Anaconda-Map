from django.conf import settings
from django.shortcuts import render


def stock_map(request):
    """Vilnius office stock 3D map. Building data is embedded in the template (no per-building names or areas)."""
    return render(request, "stock/stock.html", {
        "mapbox_token": getattr(settings, "MAPBOX_TOKEN", ""),
    })
