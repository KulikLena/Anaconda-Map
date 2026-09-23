from django.http import JsonResponse
from django.shortcuts import render
from .models import Project


def map_page(request):
    return render(request, "projects/map.html")


def projects_geojson(request):
    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [p.longitude, p.latitude]},
            "properties": {"name": p.name, "developer": p.developer, "status": p.status},
        }
        for p in Project.objects.exclude(latitude=None).exclude(longitude=None)
    ]
    return JsonResponse({"type": "FeatureCollection", "features": features})