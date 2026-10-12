from django.urls import path

from . import views

app_name = "funds"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("api/data", views.data_api, name="data_api"),
    path("api/version", views.version_api, name="version_api"),
    path("video", views.video, name="video"),
]
