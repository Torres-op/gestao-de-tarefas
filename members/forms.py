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
