from django.urls import path
from . import views

urlpatterns = [
    path("", views.map_page, name="map"),
    path("api/projects.geojson", views.projects_geojson, name="projects_geojson"),
]