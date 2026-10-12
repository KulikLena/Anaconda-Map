from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render

from . import excel_source


def dashboard(request):
    return render(request, "funds/dashboard.html", {
        "mapbox_token": getattr(settings, "MAPBOX_TOKEN", ""),
        "map_style": getattr(settings, "MAP_STYLE", ""),
        "ga_id": getattr(settings, "GA_MEASUREMENT_ID", ""),
        "live": getattr(settings, "LIVE_RELOAD", True),
    })


def video(request):
    """1080x1350 bar-race frame used to render the LinkedIn video (see funds/render_video.py)."""
    return render(request, "funds/video.html")


def data_api(request):
    """Data from "Main data file.xlsx", grouped by country.

    {"years": [2008, ...], "version": "...", "file": "Main data file.xlsx", "error": null,
     "countries": {"LT": {"name": "Lithuania", "asset_source": "ECB Data Portal", "gdp_source": "EUROSTAT",
                          "values": {"2023": {"share": 2.5, "assets": 1889.0, "gdp": 75538.8,
                                              "gdp_year": 2023, "period": "2023-Q4", "partial": false}}}}}
    """
    data, stamp, error = excel_source.load()
    if data is None:
        return JsonResponse({"years": [], "countries": {}, "version": None, "error": error}, status=503)
    resp = JsonResponse({**data, "version": stamp, "error": error})
    resp["Cache-Control"] = "no-store"
    return resp


def version_api(request):
    """Cheap check the page polls: changes whenever the workbook is saved."""
    _, stamp, error = excel_source.load()
    resp = JsonResponse({"version": stamp, "error": error})
    resp["Cache-Control"] = "no-store"
    return resp
