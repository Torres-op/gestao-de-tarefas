from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from .forms import MemberForm
from .models import Member


class MemberListView(ListView):
    model = Member
    template_name = "members/member_list.html"
    context_object_name = "members"


class MemberDetailView(DetailView):
    model = Member
    template_name = "members/member_detail.html"
    context_object_name = "member"


class MemberCreateView(SuccessMessageMixin, CreateView):
    model = Member
    form_class = MemberForm
    template_name = "members/member_form.html"
    success_message = 'Membro "%(name)s" cadastrado com sucesso.'
    extra_context = {"page_title": "Novo membro", "submit_label": "Cadastrar membro"}


class MemberUpdateView(SuccessMessageMixin, UpdateView):
    model = Member
    form_class = MemberForm
    template_name = "members/member_form.html"
    success_message = 'Membro "%(name)s" atualizado com sucesso.'
    extra_context = {"page_title": "Editar membro", "submit_label": "Salvar alterações"}


class MemberDeleteView(DeleteView):
    model = Member
    template_name = "members/member_confirm_delete.html"
    context_object_name = "member"
    success_url = reverse_lazy("members:list")

    def form_valid(self, form):
        name = self.object.name
        response = super().form_valid(form)
        messages.success(self.request, f'Membro "{name}" excluído com sucesso.')
        return response
