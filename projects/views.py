from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from core.permissions import AdminRequiredMixin, OrganizationFormMixin, OrganizationScopedMixin, admin_required
from core.tenancy import current_organization
from tasks.queries import task_table_prefetches

from .forms import ProjectForm, SprintForm
from .models import Project, Sprint


class ProjectListView(OrganizationScopedMixin, ListView):
    model = Project
    template_name = "projects/project_list.html"
    context_object_name = "projects"
    queryset = Project.objects.prefetch_related("tasks")


class ProjectDetailView(OrganizationScopedMixin, DetailView):
    model = Project
    template_name = "projects/project_detail.html"
    context_object_name = "project"
    queryset = Project.objects.prefetch_related(*task_table_prefetches("tasks", "assignee"), "sprints__tasks")


class ProjectCreateView(AdminRequiredMixin, OrganizationFormMixin, SuccessMessageMixin, CreateView):
    model = Project
    form_class = ProjectForm
    template_name = "projects/project_form.html"
    success_message = 'Projeto "%(name)s" criado com sucesso.'
    extra_context = {"page_title": "Novo projeto", "submit_label": "Criar projeto"}


class ProjectUpdateView(
    AdminRequiredMixin, OrganizationScopedMixin, OrganizationFormMixin, SuccessMessageMixin, UpdateView
):
    model = Project
    form_class = ProjectForm
    template_name = "projects/project_form.html"
    success_message = 'Projeto "%(name)s" atualizado com sucesso.'
    extra_context = {"page_title": "Editar projeto", "submit_label": "Salvar alterações"}


class ProjectDeleteView(AdminRequiredMixin, OrganizationScopedMixin, DeleteView):
    model = Project
    template_name = "projects/project_confirm_delete.html"
    context_object_name = "project"
    success_url = reverse_lazy("projects:list")

    def form_valid(self, form):
        name = self.object.name
        response = super().form_valid(form)
        messages.success(self.request, f'Projeto "{name}" excluído com sucesso.')
        return response


def organization_sprints(request):
    return Sprint.objects.select_related("project").filter(project__organization=current_organization(request))


class SprintDetailView(DetailView):
    model = Sprint
    template_name = "projects/sprint_detail.html"
    context_object_name = "sprint"

    def get_queryset(self):
        return organization_sprints(self.request).prefetch_related(
            *task_table_prefetches("tasks", "assignee", "project")
        )


@admin_required
def sprint_create(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk, organization=current_organization(request))
    form = SprintForm(request.POST or None, project=project)
    if request.method == "POST" and form.is_valid():
        sprint = form.save()
        messages.success(request, f'Sprint "{sprint.name}" criada.')
        return redirect(sprint)
    context = {
        "form": form,
        "project": project,
        "page_title": "Nova sprint",
        "submit_label": "Criar sprint",
    }
    return render(request, "projects/sprint_form.html", context)


@admin_required
def sprint_update(request, pk):
    sprint = get_object_or_404(organization_sprints(request), pk=pk)
    form = SprintForm(request.POST or None, instance=sprint, project=sprint.project)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f'Sprint "{sprint.name}" atualizada.')
        return redirect(sprint)
    context = {
        "form": form,
        "project": sprint.project,
        "page_title": "Editar sprint",
        "submit_label": "Salvar alterações",
    }
    return render(request, "projects/sprint_form.html", context)


@admin_required
def sprint_delete(request, pk):
    sprint = get_object_or_404(organization_sprints(request), pk=pk)
    if request.method == "POST":
        project = sprint.project
        sprint.delete()
        messages.success(request, f'Sprint "{sprint.name}" excluída. Suas tarefas voltaram para o backlog.')
        return redirect(project)
    return render(request, "projects/sprint_confirm_delete.html", {"sprint": sprint})
