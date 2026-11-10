from django.shortcuts import render


def index(request):
    """Short, anonymised portfolio (public)."""
    return render(request, "portfolio/index.html")


def full(request):
    """Full portfolio with all slides. Contains project-specific details: not for public use."""
    return render(request, "portfolio/index_full.html")
