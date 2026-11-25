from django import forms

from .models import Member


class MemberForm(forms.ModelForm):
    class Meta:
        model = Member
        fields = ["name", "email", "role", "is_active"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Nome completo"}),
            "email": forms.EmailInput(attrs={"placeholder": "nome@exemplo.com"}),
            "role": forms.TextInput(attrs={"placeholder": "Ex.: Desenvolvedor(a)"}),
        }
        help_texts = {
            "role": "Cargo ou função da pessoa na equipe.",
            "is_active": "Membros inativos não podem ser escolhidos como responsáveis por novas tarefas.",
        }

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.organization_id is None:
            self.instance.organization = organization

    def clean_email(self):
        email = self.cleaned_data["email"]
        duplicated = Member.objects.filter(
            organization_id=self.instance.organization_id, email__iexact=email
        ).exclude(pk=self.instance.pk)
        if duplicated.exists():
            raise forms.ValidationError("Já existe um membro com este e-mail na sua organização.")
        return email
