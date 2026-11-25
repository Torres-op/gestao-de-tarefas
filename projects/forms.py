from django import forms

from .models import Project, Sprint


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ["name", "description", "start_date", "due_date"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Ex.: Sistema Acadêmico"}),
            "description": forms.Textarea(attrs={"placeholder": "Objetivo e escopo do projeto"}),
            "start_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "due_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.organization_id is None:
            self.instance.organization = organization


class SprintForm(forms.ModelForm):
    class Meta:
        model = Sprint
        fields = ["name", "goal", "start_date", "end_date"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Ex.: Sprint 1"}),
            "goal": forms.Textarea(attrs={"placeholder": "O que a equipe se compromete a entregar"}),
            "start_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "end_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }

    def __init__(self, *args, project, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.project = project
