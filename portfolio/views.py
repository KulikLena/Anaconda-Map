from django.conf import settings
from django.shortcuts import render


def _ctx():
    return {"ga_id": getattr(settings, "GA_MEASUREMENT_ID", "")}


def index(request):
    """Short, anonymised portfolio (public)."""
    return render(request, "portfolio/index.html", _ctx())


def full(request):
    """Full portfolio with all slides. Contains project-specific details: not for public use."""
    return render(request, "portfolio/index_full.html", _ctx())
