from rest_framework.routers import DefaultRouter

from .views import (
    MemberViewSet,
    ProjectViewSet,
    SprintViewSet,
    SubtaskViewSet,
    TaskDependencyViewSet,
    TaskViewSet,
)

app_name = "api"

router = DefaultRouter()
router.register("projects", ProjectViewSet, basename="project")
router.register("sprints", SprintViewSet, basename="sprint")
router.register("members", MemberViewSet, basename="member")
router.register("tasks", TaskViewSet, basename="task")
router.register("subtasks", SubtaskViewSet, basename="subtask")
router.register("dependencies", TaskDependencyViewSet, basename="dependency")

urlpatterns = router.urls
