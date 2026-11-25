import copy

from django.core.exceptions import NON_FIELD_ERRORS
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework.settings import api_settings

from core.tenancy import get_profile
from members.models import Member
from projects.models import Project, Sprint
from tasks.models import Subtask, Task, TaskDependency


def request_organization(context):
    request = context.get("request")
    profile = get_profile(getattr(request, "user", None))
    return profile.organization if profile else None


def django_error_detail(error):
    if hasattr(error, "error_dict"):
        return {
            api_settings.NON_FIELD_ERRORS_KEY if field == NON_FIELD_ERRORS else field: messages
            for field, messages in error.message_dict.items()
        }
    return {api_settings.NON_FIELD_ERRORS_KEY: error.messages}


class OrganizationRelatedField(serializers.PrimaryKeyRelatedField):
    def __init__(self, model, organization_lookup, **kwargs):
        self.model = model
        self.organization_lookup = organization_lookup
        super().__init__(**kwargs)

    def get_queryset(self):
        organization = request_organization(self.context)
        queryset = self.model._default_manager.all()
        if organization is None:
            return queryset.none()
        return queryset.filter(**{self.organization_lookup: organization})


class ModelCleanMixin:
    def get_clean_extra_attrs(self):
        if self.instance is None and hasattr(self.Meta.model, "organization_id"):
            return {"organization": request_organization(self.context)}
        return {}

    def build_clean_instance(self, attrs):
        values = {**self.get_clean_extra_attrs(), **attrs}
        if self.instance is None:
            return self.Meta.model(**values)
        instance = copy.copy(self.instance)
        for name, value in values.items():
            setattr(instance, name, value)
        return instance

    def validate(self, attrs):
        attrs = super().validate(attrs)
        instance = self.build_clean_instance(attrs)
        try:
            instance.clean()
        except DjangoValidationError as error:
            raise serializers.ValidationError(django_error_detail(error))
        return attrs


class ProjectSerializer(ModelCleanMixin, serializers.ModelSerializer):
    task_count = serializers.IntegerField(read_only=True)
    completed_task_count = serializers.IntegerField(read_only=True)
    progress_percent = serializers.IntegerField(read_only=True)

    class Meta:
        model = Project
        fields = [
            "id",
            "name",
            "description",
            "start_date",
            "due_date",
            "task_count",
            "completed_task_count",
            "progress_percent",
            "created_at",
        ]
        read_only_fields = ["created_at"]


class SprintSerializer(ModelCleanMixin, serializers.ModelSerializer):
    project = OrganizationRelatedField(Project, "organization")
    project_name = serializers.CharField(source="project.name", read_only=True)
    state = serializers.CharField(read_only=True)
    state_label = serializers.CharField(read_only=True)
    duration_days = serializers.IntegerField(read_only=True)
    task_count = serializers.IntegerField(read_only=True)
    completed_task_count = serializers.IntegerField(read_only=True)
    progress_percent = serializers.IntegerField(read_only=True)

    class Meta:
        model = Sprint
        fields = [
            "id",
            "project",
            "project_name",
            "name",
            "goal",
            "start_date",
            "end_date",
            "state",
            "state_label",
            "duration_days",
            "task_count",
            "completed_task_count",
            "progress_percent",
            "created_at",
        ]
        read_only_fields = ["created_at"]
        validators = []


class MemberSerializer(ModelCleanMixin, serializers.ModelSerializer):
    class Meta:
        model = Member
        fields = ["id", "name", "email", "role", "is_active", "created_at"]
        read_only_fields = ["created_at"]

    def validate_email(self, value):
        organization = request_organization(self.context)
        duplicated = Member.objects.filter(organization=organization, email__iexact=value)
        if self.instance is not None:
            duplicated = duplicated.exclude(pk=self.instance.pk)
        if duplicated.exists():
            raise serializers.ValidationError("Já existe um membro com este e-mail na sua organização.")
        return value


class TaskSerializer(ModelCleanMixin, serializers.ModelSerializer):
    project = OrganizationRelatedField(Project, "organization")
    sprint = OrganizationRelatedField(
        Sprint, "project__organization", required=False, allow_null=True
    )
    assignee = OrganizationRelatedField(
        Member, "organization", required=False, allow_null=True
    )
    project_name = serializers.CharField(source="project.name", read_only=True)
    sprint_name = serializers.CharField(source="sprint.name", read_only=True, default=None)
    assignee_name = serializers.CharField(source="assignee.name", read_only=True, default=None)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    is_blocked = serializers.BooleanField(read_only=True)
    blocking_reason = serializers.CharField(read_only=True)
    subtask_count = serializers.IntegerField(read_only=True)
    completed_subtask_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Task
        fields = [
            "id",
            "project",
            "project_name",
            "sprint",
            "sprint_name",
            "title",
            "description",
            "assignee",
            "assignee_name",
            "status",
            "status_label",
            "due_date",
            "is_blocked",
            "blocking_reason",
            "subtask_count",
            "completed_subtask_count",
            "started_at",
            "completed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["started_at", "completed_at", "created_at", "updated_at"]

    def validate_assignee(self, value):
        unchanged = self.instance is not None and value is not None and self.instance.assignee_id == value.pk
        if value is not None and not value.is_active and not unchanged:
            raise serializers.ValidationError(
                "Membros inativos não podem ser escolhidos como responsáveis por tarefas."
            )
        return value


class SubtaskSerializer(ModelCleanMixin, serializers.ModelSerializer):
    task = OrganizationRelatedField(Task, "project__organization")
    task_title = serializers.CharField(source="task.title", read_only=True)

    class Meta:
        model = Subtask
        fields = ["id", "task", "task_title", "title", "is_done", "created_at"]
        read_only_fields = ["created_at"]


class TaskDependencySerializer(ModelCleanMixin, serializers.ModelSerializer):
    task = OrganizationRelatedField(Task, "project__organization")
    depends_on = OrganizationRelatedField(Task, "project__organization")
    task_title = serializers.CharField(source="task.title", read_only=True)
    depends_on_title = serializers.CharField(source="depends_on.title", read_only=True)
    depends_on_status = serializers.CharField(source="depends_on.status", read_only=True)

    class Meta:
        model = TaskDependency
        fields = [
            "id",
            "task",
            "task_title",
            "depends_on",
            "depends_on_title",
            "depends_on_status",
            "created_at",
        ]
        read_only_fields = ["created_at"]
        validators = []
