from django.urls import path

from .api_views import DashboardAPIView, SprintBurndownAPIView

app_name = "dashboard_api"

urlpatterns = [
    path("", DashboardAPIView.as_view(), name="summary"),
    path("burndown/", SprintBurndownAPIView.as_view(), name="burndown"),
]
