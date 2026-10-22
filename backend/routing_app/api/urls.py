from django.urls import path

from .views import AnalyzeView, GeocodeView, HealthView

urlpatterns = [
    path("health", HealthView.as_view(), name="health"),
    path("geocode", GeocodeView.as_view(), name="geocode"),
    path("analyze", AnalyzeView.as_view(), name="analyze"),
]
