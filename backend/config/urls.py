from django.urls import include, path

urlpatterns = [
    path("api/", include("routing_app.api.urls")),
]
