from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from core.permissions import AdminRequiredMixin, OrganizationFormMixin, OrganizationScopedMixin
from tasks.queries import task_table_prefetches

from .forms import MemberForm
from .models import Member


class MemberListView(OrganizationScopedMixin, ListView):
    model = Member
    template_name = "members/member_list.html"
    context_object_name = "members"


class MemberDetailView(OrganizationScopedMixin, DetailView):
    model = Member
    template_name = "members/member_detail.html"
    context_object_name = "member"
    queryset = Member.objects.prefetch_related(*task_table_prefetches("tasks", "project"))


class MemberCreateView(AdminRequiredMixin, OrganizationFormMixin, SuccessMessageMixin, CreateView):
    model = Member
    form_class = MemberForm
    template_name = "members/member_form.html"
    success_message = 'Membro "%(name)s" cadastrado com sucesso.'
    extra_context = {"page_title": "Novo membro", "submit_label": "Cadastrar membro"}


class MemberUpdateView(
    AdminRequiredMixin, OrganizationScopedMixin, OrganizationFormMixin, SuccessMessageMixin, UpdateView
):
    model = Member
    form_class = MemberForm
    template_name = "members/member_form.html"
    success_message = 'Membro "%(name)s" atualizado com sucesso.'
    extra_context = {"page_title": "Editar membro", "submit_label": "Salvar alterações"}


class MemberDeleteView(AdminRequiredMixin, OrganizationScopedMixin, DeleteView):
    model = Member
    template_name = "members/member_confirm_delete.html"
    context_object_name = "member"
    success_url = reverse_lazy("members:list")

    def form_valid(self, form):
        name = self.object.name
        response = super().form_valid(form)
        messages.success(self.request, f'Membro "{name}" excluído com sucesso.')
        return response
