from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.tenancy import current_organization
from members.models import Member
from projects.models import Project, Sprint
from tasks.models import Subtask, Task, TaskDependency
from tasks.queries import dependencies_prefetch, dependents_prefetch

from .permissions import HasOrganizationProfile, IsOrgAdminOrReadOnly, IsOrgAdminToDelete
from .serializers import (
    MemberSerializer,
    ProjectSerializer,
    SprintSerializer,
    SubtaskSerializer,
    TaskDependencySerializer,
    TaskSerializer,
)


class OrganizationViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, HasOrganizationProfile]
    organization_field = "organization"
    query_filters = {}

    def get_organization(self):
        return current_organization(self.request)

    def get_queryset(self):
        queryset = super().get_queryset().filter(**{self.organization_field: self.get_organization()})
        return self.apply_query_filters(queryset)

    def apply_query_filters(self, queryset):
        for param, lookup in self.query_filters.items():
            value = self.request.query_params.get(param, "")
            if value.isdigit():
                queryset = queryset.filter(**{lookup: int(value)})
        return queryset

    def error_response(self, error):
        return Response({"detail": " ".join(error.messages)}, status=status.HTTP_400_BAD_REQUEST)


class OrganizationOwnedViewSet(OrganizationViewSet):
    def perform_create(self, serializer):
        serializer.save(organization=self.get_organization())


class ProjectViewSet(OrganizationOwnedViewSet):
    queryset = Project.objects.prefetch_related("tasks")
    serializer_class = ProjectSerializer
    permission_classes = [*OrganizationViewSet.permission_classes, IsOrgAdminOrReadOnly]


class MemberViewSet(OrganizationOwnedViewSet):
    queryset = Member.objects.all()
    serializer_class = MemberSerializer
    permission_classes = [*OrganizationViewSet.permission_classes, IsOrgAdminOrReadOnly]


class SprintViewSet(OrganizationViewSet):
    queryset = Sprint.objects.select_related("project").prefetch_related("tasks")
    serializer_class = SprintSerializer
    permission_classes = [*OrganizationViewSet.permission_classes, IsOrgAdminOrReadOnly]
    organization_field = "project__organization"
    query_filters = {"project": "project_id"}


class TaskViewSet(OrganizationViewSet):
    queryset = Task.objects.select_related("project", "sprint", "assignee").prefetch_related(
        "subtasks", dependencies_prefetch(), dependents_prefetch()
    )
    serializer_class = TaskSerializer
    permission_classes = [*OrganizationViewSet.permission_classes, IsOrgAdminToDelete]
    organization_field = "project__organization"
    query_filters = {"project": "project_id", "sprint": "sprint_id", "assignee": "assignee_id"}

    def apply_query_filters(self, queryset):
        queryset = super().apply_query_filters(queryset)
        task_status = self.request.query_params.get("status", "")
        if task_status in Task.Status.values:
            queryset = queryset.filter(status=task_status)
        return queryset

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        task = self.get_object()
        try:
            task.complete()
        except DjangoValidationError as error:
            return self.error_response(error)
        return Response(self.get_serializer(task).data)

    @action(detail=True, methods=["post"])
    def reopen(self, request, pk=None):
        task = self.get_object()
        try:
            task.reopen()
        except DjangoValidationError as error:
            return self.error_response(error)
        return Response(self.get_serializer(task).data)


class SubtaskViewSet(OrganizationViewSet):
    queryset = Subtask.objects.select_related("task")
    serializer_class = SubtaskSerializer
    organization_field = "task__project__organization"
    query_filters = {"task": "task_id"}

    @action(detail=True, methods=["post"])
    def toggle(self, request, pk=None):
        subtask = self.get_object()
        try:
            subtask.toggle()
        except DjangoValidationError as error:
            return self.error_response(error)
        return Response(self.get_serializer(subtask).data)


class TaskDependencyViewSet(OrganizationViewSet):
    queryset = TaskDependency.objects.select_related("task", "depends_on")
    serializer_class = TaskDependencySerializer
    organization_field = "task__project__organization"
    query_filters = {"task": "task_id", "depends_on": "depends_on_id"}
