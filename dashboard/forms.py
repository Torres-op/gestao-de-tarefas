from datetime import date

from django import forms

from projects.models import Project, Sprint

from .metrics import resolve_period

DATE_INPUT_FORMATS = ["%Y-%m-%d", "%d/%m/%Y"]
MIN_DATE = date(2000, 1, 1)
MAX_DATE = date(2100, 12, 31)
MAX_PERIOD_DAYS = 1096


def date_field(label):
    return forms.DateField(
        label=label,
        required=False,
        input_formats=DATE_INPUT_FORMATS,
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )


class PeriodForm(forms.Form):
    start = date_field("Início")
    end = date_field("Fim")

    def clean_start(self):
        return self.validate_range(self.cleaned_data.get("start"))

    def clean_end(self):
        return self.validate_range(self.cleaned_data.get("end"))

    def validate_range(self, value):
        if value and not MIN_DATE <= value <= MAX_DATE:
            raise forms.ValidationError("Informe uma data entre 2000 e 2100.")
        return value

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get("start")
        end = cleaned_data.get("end")
        if start and end and end < start:
            self.add_error("end", "A data final não pode ser anterior à data inicial.")
        elif not self.errors:
            effective_start, effective_end = resolve_period(start, end)
            if (effective_end - effective_start).days >= MAX_PERIOD_DAYS:
                self.add_error("end" if end else "start", "O período pode ter no máximo 3 anos.")
        return cleaned_data


class DashboardFilterForm(PeriodForm):
    project = forms.ModelChoiceField(
        label="Projeto",
        queryset=Project.objects.none(),
        required=False,
        empty_label="Todos os projetos",
    )
    sprint = forms.ModelChoiceField(
        label="Sprint",
        queryset=Sprint.objects.none(),
        required=False,
        empty_label="Todas as sprints",
    )

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["project"].queryset = Project.objects.filter(organization=organization).order_by("name")
        self.fields["sprint"].queryset = (
            Sprint.objects.filter(project__organization=organization)
            .select_related("project")
            .order_by("project__name", "-start_date")
        )

    def clean(self):
        cleaned_data = super().clean()
        project = cleaned_data.get("project")
        sprint = cleaned_data.get("sprint")
        if project and sprint and sprint.project_id != project.pk:
            self.add_error("sprint", "A sprint escolhida não pertence ao projeto selecionado.")
        return cleaned_data
