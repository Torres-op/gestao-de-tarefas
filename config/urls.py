from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", TemplateView.as_view(template_name="home.html"), name="home"),
    path("projects/", include("projects.urls")),
    path("members/", include("members.urls")),
    path("tasks/", include("tasks.urls")),
]
