from django.urls import path

from . import views

app_name = "tasks"

urlpatterns = [
    path("", views.TaskListView.as_view(), name="list"),
    path("new/", views.TaskCreateView.as_view(), name="create"),
    path("<int:pk>/", views.TaskDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.TaskUpdateView.as_view(), name="update"),
    path("<int:pk>/delete/", views.TaskDeleteView.as_view(), name="delete"),
    path("<int:pk>/complete/", views.task_complete, name="complete"),
    path("<int:pk>/reopen/", views.task_reopen, name="reopen"),
    path("<int:task_pk>/dependencies/new/", views.dependency_create, name="dependency_create"),
    path("dependencies/<int:pk>/delete/", views.dependency_delete, name="dependency_delete"),
    path("<int:task_pk>/subtasks/new/", views.subtask_create, name="subtask_create"),
    path("subtasks/<int:pk>/edit/", views.subtask_update, name="subtask_update"),
    path("subtasks/<int:pk>/delete/", views.subtask_delete, name="subtask_delete"),
    path("subtasks/<int:pk>/toggle/", views.subtask_toggle, name="subtask_toggle"),
]
