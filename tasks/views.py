from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from core.pagination import LenientPaginationMixin
from core.permissions import AdminRequiredMixin, OrganizationFormMixin
from core.tenancy import current_organization
from projects.models import Project, Sprint

from .forms import SubtaskForm, TaskDependencyForm, TaskForm
from .models import Subtask, Task, TaskDependency
from .queries import dependencies_prefetch, dependents_prefetch


def organization_tasks(request):
    return Task.objects.filter(project__organization=current_organization(request))


def organization_subtasks(request):
    return Subtask.objects.select_related("task").filter(task__project__organization=current_organization(request))


class OrganizationTaskMixin:
    def get_queryset(self):
        return super().get_queryset().filter(project__organization=current_organization(self.request))


class TaskListView(OrganizationTaskMixin, LenientPaginationMixin, ListView):
    model = Task
    paginate_by = 25
    template_name = "tasks/task_list.html"
    context_object_name = "tasks"

    def get_selected_id(self, name):
        value = self.request.GET.get(name, "")
        return int(value) if value.isdigit() else None

    def get_selected_status(self):
        status = self.request.GET.get("status", "")
        return status if status in Task.Status.values else ""

    def get_queryset(self):
        queryset = (
            super()
            .get_queryset()
            .select_related("project", "assignee", "sprint")
            .prefetch_related("subtasks", dependencies_prefetch())
        )
        project_id = self.get_selected_id("project")
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        sprint_id = self.get_selected_id("sprint")
        if sprint_id:
            queryset = queryset.filter(sprint_id=sprint_id)
        status = self.get_selected_status()
        if status:
            queryset = queryset.filter(status=status)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        organization = current_organization(self.request)
        context["projects"] = Project.objects.filter(organization=organization)
        context["sprints"] = Sprint.objects.filter(project__organization=organization).select_related("project")
        context["status_choices"] = Task.Status.choices
        context["selected_project_id"] = self.get_selected_id("project")
        context["selected_sprint_id"] = self.get_selected_id("sprint")
        context["selected_status"] = self.get_selected_status()
        return context


class TaskDetailView(OrganizationTaskMixin, DetailView):
    model = Task
    template_name = "tasks/task_detail.html"
    context_object_name = "task"
    queryset = Task.objects.select_related("project", "assignee", "sprint").prefetch_related(
        "subtasks", dependencies_prefetch(), dependents_prefetch()
    )


class TaskCreateView(OrganizationFormMixin, SuccessMessageMixin, CreateView):
    model = Task
    form_class = TaskForm
    template_name = "tasks/task_form.html"
    success_message = 'Tarefa "%(title)s" criada com sucesso.'
    extra_context = {"page_title": "Nova tarefa", "submit_label": "Criar tarefa"}

    def get_initial(self):
        initial = super().get_initial()
        for name in ("project", "sprint"):
            value = self.request.GET.get(name, "")
            if value.isdigit():
                initial[name] = value
        return initial


class TaskUpdateView(OrganizationTaskMixin, OrganizationFormMixin, SuccessMessageMixin, UpdateView):
    model = Task
    form_class = TaskForm
    template_name = "tasks/task_form.html"
    success_message = 'Tarefa "%(title)s" atualizada com sucesso.'
    extra_context = {"page_title": "Editar tarefa", "submit_label": "Salvar alterações"}


class TaskDeleteView(AdminRequiredMixin, OrganizationTaskMixin, DeleteView):
    model = Task
    template_name = "tasks/task_confirm_delete.html"
    context_object_name = "task"

    def get_success_url(self):
        return self.object.project.get_absolute_url()

    def form_valid(self, form):
        title = self.object.title
        response = super().form_valid(form)
        messages.success(self.request, f'Tarefa "{title}" excluída com sucesso.')
        return response


def subtask_create(request, task_pk):
    task = get_object_or_404(organization_tasks(request), pk=task_pk)
    if request.method == "POST":
        form = SubtaskForm(request.POST, task=task)
        if form.is_valid():
            subtask = form.save()
            messages.success(request, f'Subtarefa "{subtask.title}" adicionada.')
            return redirect(task)
    else:
        form = SubtaskForm(task=task)
    context = {
        "form": form,
        "task": task,
        "page_title": "Nova subtarefa",
        "submit_label": "Adicionar subtarefa",
    }
    return render(request, "tasks/subtask_form.html", context)


def subtask_update(request, pk):
    subtask = get_object_or_404(organization_subtasks(request), pk=pk)
    if request.method == "POST":
        form = SubtaskForm(request.POST, instance=subtask, task=subtask.task)
        if form.is_valid():
            form.save()
            messages.success(request, f'Subtarefa "{subtask.title}" atualizada.')
            return redirect(subtask.task)
    else:
        form = SubtaskForm(instance=subtask, task=subtask.task)
    context = {
        "form": form,
        "task": subtask.task,
        "page_title": "Editar subtarefa",
        "submit_label": "Salvar alterações",
    }
    return render(request, "tasks/subtask_form.html", context)


def subtask_delete(request, pk):
    subtask = get_object_or_404(organization_subtasks(request), pk=pk)
    if request.method == "POST":
        subtask.delete()
        messages.success(request, f'Subtarefa "{subtask.title}" excluída.')
        return redirect(subtask.task)
    return render(request, "tasks/subtask_confirm_delete.html", {"subtask": subtask})


@require_POST
def subtask_toggle(request, pk):
    subtask = get_object_or_404(organization_subtasks(request), pk=pk)
    try:
        subtask.toggle()
    except ValidationError as error:
        messages.error(
            request,
            f'Não é possível reabrir a subtarefa "{subtask.title}". {" ".join(error.messages)}',
        )
    else:
        if subtask.is_done:
            messages.success(request, f'Subtarefa "{subtask.title}" marcada como concluída.')
        else:
            messages.info(request, f'Subtarefa "{subtask.title}" reaberta.')
    return redirect(subtask.task)


@require_POST
def task_complete(request, pk):
    task = get_object_or_404(
        organization_tasks(request).prefetch_related("dependencies__depends_on", "subtasks"), pk=pk
    )
    try:
        task.complete()
    except ValidationError as error:
        messages.error(request, f'Não é possível concluir "{task.title}". {" ".join(error.messages)}')
    else:
        messages.success(request, f'Tarefa "{task.title}" concluída.')
    return redirect(task)


@require_POST
def task_reopen(request, pk):
    task = get_object_or_404(organization_tasks(request).prefetch_related("dependents__task"), pk=pk)
    try:
        task.reopen()
    except ValidationError as error:
        messages.error(request, f'Não é possível reabrir "{task.title}". {" ".join(error.messages)}')
    else:
        messages.success(request, f'Tarefa "{task.title}" reaberta.')
    return redirect(task)


def dependency_create(request, task_pk):
    task = get_object_or_404(organization_tasks(request).select_related("project"), pk=task_pk)
    if request.method == "POST":
        form = TaskDependencyForm(request.POST, task=task)
        if form.is_valid():
            dependency = form.save()
            messages.success(
                request,
                f'A tarefa "{task.title}" agora depende de "{dependency.depends_on.title}".',
            )
            return redirect(task)
    else:
        form = TaskDependencyForm(task=task)
    context = {
        "form": form,
        "task": task,
        "has_candidates": form.fields["depends_on"].queryset.exists(),
        "page_title": "Nova dependência",
        "submit_label": "Adicionar dependência",
    }
    return render(request, "tasks/dependency_form.html", context)


@require_POST
def dependency_delete(request, pk):
    dependency = get_object_or_404(
        TaskDependency.objects.select_related("task", "depends_on").filter(
            task__project__organization=current_organization(request)
        ),
        pk=pk,
    )
    dependency.delete()
    messages.success(
        request,
        f'A tarefa "{dependency.task.title}" não depende mais de "{dependency.depends_on.title}".',
    )
    return redirect(dependency.task)
