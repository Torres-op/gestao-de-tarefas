from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.tenancy import get_profile
from projects.models import Sprint

from . import metrics
from .services import dashboard_payload, default_burndown_sprint, parse_filters


class HasProfile(BasePermission):
    message = (
        "Seu usuário não está vinculado a nenhuma organização. "
        "Peça a um administrador para configurar o seu perfil."
    )

    def has_permission(self, request, view):
        return get_profile(request.user) is not None


class DashboardAPIView(APIView):
    permission_classes = [IsAuthenticated, HasProfile]

    def get(self, request):
        profile = get_profile(request.user)
        today = timezone.localdate()
        form, filters = parse_filters(request.query_params, profile.organization, today)
        if form.errors:
            return Response({"errors": form.errors}, status=status.HTTP_400_BAD_REQUEST)
        return Response(dashboard_payload(profile.organization, filters, profile.is_admin, today))


class SprintBurndownAPIView(APIView):
    permission_classes = [IsAuthenticated, HasProfile]

    def get(self, request):
        profile = get_profile(request.user)
        organization = profile.organization
        today = timezone.localdate()
        value = request.query_params.get("sprint", "")
        if value:
            if not value.isdigit():
                return Response(
                    {"errors": {"sprint": ["Informe o identificador numérico da sprint."]}},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            sprints = Sprint.objects.filter(project__organization=organization).select_related("project")
            sprint = get_object_or_404(sprints, pk=int(value))
        else:
            sprint = default_burndown_sprint(organization, today=today)
            if sprint is None:
                raise NotFound("Nenhuma sprint cadastrada na organização.")
        tasks = metrics.organization_tasks(organization)
        return Response(metrics.sprint_burndown(sprint, today, tasks))
