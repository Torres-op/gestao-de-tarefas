from django.urls import path

from . import views

app_name = "projects"

urlpatterns = [
    path("", views.ProjectListView.as_view(), name="list"),
    path("new/", views.ProjectCreateView.as_view(), name="create"),
    path("<int:pk>/", views.ProjectDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.ProjectUpdateView.as_view(), name="update"),
    path("<int:pk>/delete/", views.ProjectDeleteView.as_view(), name="delete"),
    path("<int:project_pk>/sprints/new/", views.sprint_create, name="sprint_create"),
    path("sprints/<int:pk>/", views.SprintDetailView.as_view(), name="sprint_detail"),
    path("sprints/<int:pk>/edit/", views.sprint_update, name="sprint_update"),
    path("sprints/<int:pk>/delete/", views.sprint_delete, name="sprint_delete"),
]
