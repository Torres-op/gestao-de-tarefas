from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.views.generic import TemplateView

from core.forms import LoginForm

admin.site.site_header = "Grello"
admin.site.site_title = "Grello"
admin.site.index_title = "Administração"

urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(authentication_form=LoginForm, redirect_authenticated_user=True),
        name="login",
    ),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", TemplateView.as_view(template_name="home.html"), name="home"),
    path("dashboard/", include("dashboard.urls")),
    path("projects/", include("projects.urls")),
    path("members/", include("members.urls")),
    path("tasks/", include("tasks.urls")),
    path("api/auth/", include("rest_framework.urls")),
    path("api/dashboard/", include("dashboard.api_urls")),
    path("api/", include("api.urls")),
]
