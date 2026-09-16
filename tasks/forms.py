from django import forms
from django.db.models import Q

from members.models import Member

from .models import Subtask, Task, TaskDependency


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ["project", "title", "description", "assignee", "status", "due_date"]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Ex.: Modelar o banco de dados"}),
            "description": forms.Textarea(attrs={"placeholder": "O que precisa ser feito"}),
            "due_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        available = Q(is_active=True)
        if self.instance.assignee_id:
            available |= Q(pk=self.instance.assignee_id)
        self.fields["assignee"].queryset = Member.objects.filter(available)
        self.fields["assignee"].empty_label = "Sem responsável"


class SubtaskForm(forms.ModelForm):
    class Meta:
        model = Subtask
        fields = ["title", "is_done"]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Ex.: Desenhar o diagrama ER"}),
        }


class TaskDependencyForm(forms.ModelForm):
    class Meta:
        model = TaskDependency
        fields = ["depends_on"]

    def __init__(self, *args, task, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.task = task
        already_required = TaskDependency.objects.filter(task=task).values_list("depends_on_id", flat=True)
        self.fields["depends_on"].queryset = (
            Task.objects.filter(project_id=task.project_id)
            .exclude(pk=task.pk)
            .exclude(pk__in=already_required)
        )
        self.fields["depends_on"].label = "Esta tarefa depende de"
        self.fields["depends_on"].empty_label = "Selecione uma tarefa"
        self.fields["depends_on"].help_text = "Somente tarefas do mesmo projeto podem ser pré-requisitos."
