from django.urls import path

from routing import views

app_name = "routing"

urlpatterns = [
    path("health", views.HealthView.as_view(), name="health"),
    path("routes/analyze", views.AnalyzeView.as_view(), name="analyze"),
    path("heatmap", views.HeatmapView.as_view(), name="heatmap"),
    path("geocode", views.GeocodeView.as_view(), name="geocode"),
]
