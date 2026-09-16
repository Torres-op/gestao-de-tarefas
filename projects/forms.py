from django import forms

from .models import Project


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
