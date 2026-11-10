from django.conf import settings
from django.shortcuts import render


def _ctx():
    return {"mapbox_token": getattr(settings, "MAPBOX_TOKEN", "")}


def stock_map(request):
    """Vilnius office stock 3D map. Building data is embedded in the template (no per-building names or areas)."""
    return render(request, "stock/stock.html", _ctx())


def route_map(request):
    """Shortest driving route through all office buildings (travelling salesman), animated."""
    return render(request, "stock/route.html", _ctx())
