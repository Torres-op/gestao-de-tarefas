from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from core.testing import make_admin, make_member, make_operator, make_organization

from .forms import MemberForm
from .models import Member


class MembersFixtureMixin:
    @classmethod
    def setUpTestData(cls):
        cls.organization = make_organization("Organização A")
        cls.admin = make_admin("admin.a", cls.organization)
        cls.operator = make_operator("operador.a", cls.organization)
        cls.member = make_member(cls.organization, "Ana Souza", email="ana@exemplo.com")

        cls.other_organization = make_organization("Organização B")
        cls.other_admin = make_admin("admin.b", cls.other_organization)
        cls.other_member = make_member(cls.other_organization, "Bruno Lima", email="bruno@exemplo.com")


def member_data(**overrides):
    data = {"name": "Carla Dias", "email": "carla@exemplo.com", "role": "Designer", "is_active": "on"}
    data.update(overrides)
    return data


class MemberEmailUniquenessTests(MembersFixtureMixin, TestCase):
    def test_form_rejects_duplicated_email_in_same_organization(self):
        form = MemberForm(data=member_data(email="ana@exemplo.com"), organization=self.organization)
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_form_comparison_is_case_insensitive(self):
        form = MemberForm(data=member_data(email="ANA@Exemplo.com"), organization=self.organization)
        self.assertFalse(form.is_valid())
        self.assertIn("Já existe um membro com este e-mail", form.errors["email"][0])

    def test_form_accepts_same_email_in_another_organization(self):
        form = MemberForm(data=member_data(email="ana@exemplo.com"), organization=self.other_organization)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().organization, self.other_organization)

    def test_form_editing_member_keeps_its_own_email(self):
        form = MemberForm(
            data=member_data(name="Ana S.", email="ana@exemplo.com"), instance=self.member, organization=self.organization
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_form_editing_member_cannot_take_email_of_colleague(self):
        colleague = make_member(self.organization, "Diego", email="diego@exemplo.com")
        form = MemberForm(data=member_data(email="ana@exemplo.com"), instance=colleague, organization=self.organization)
        self.assertFalse(form.is_valid())

    def test_form_does_not_change_organization_of_existing_member(self):
        form = MemberForm(
            data=member_data(name="Ana", email="ana@exemplo.com"), instance=self.member, organization=self.other_organization
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().organization, self.organization)

    def test_database_rejects_duplicated_email_in_same_organization(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Member.objects.create(organization=self.organization, name="Outra Ana", email="ana@exemplo.com")

    def test_database_accepts_same_email_in_another_organization(self):
        Member.objects.create(organization=self.other_organization, name="Outra Ana", email="ana@exemplo.com")
        self.assertEqual(Member.objects.filter(email="ana@exemplo.com").count(), 2)


class MemberRoleTests(MembersFixtureMixin, TestCase):
    def test_operator_sees_members_without_admin_buttons(self):
        self.client.force_login(self.operator)
        response = self.client.get(reverse("members:list"))
        self.assertContains(response, "Ana Souza")
        self.assertNotContains(response, reverse("members:create"))
        self.assertNotContains(response, reverse("members:update", args=[self.member.pk]))
        detail = self.client.get(self.member.get_absolute_url())
        self.assertEqual(detail.status_code, 200)
        self.assertNotContains(detail, reverse("members:delete", args=[self.member.pk]))

    def test_admin_sees_admin_buttons(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("members:list"))
        self.assertContains(response, reverse("members:create"))
        self.assertContains(response, reverse("members:update", args=[self.member.pk]))

    def test_operator_cannot_create_edit_or_delete_member(self):
        self.client.force_login(self.operator)
        self.assertEqual(self.client.get(reverse("members:create")).status_code, 403)
        self.assertEqual(self.client.post(reverse("members:create"), member_data()).status_code, 403)
        self.assertEqual(
            self.client.post(reverse("members:update", args=[self.member.pk]), member_data()).status_code, 403
        )
        self.assertEqual(self.client.post(reverse("members:delete", args=[self.member.pk])).status_code, 403)
        self.assertFalse(Member.objects.filter(email="carla@exemplo.com").exists())
        self.assertTrue(Member.objects.filter(pk=self.member.pk).exists())

    def test_admin_creates_member_in_own_organization(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("members:create"), member_data())
        member = Member.objects.get(email="carla@exemplo.com")
        self.assertRedirects(response, member.get_absolute_url())
        self.assertEqual(member.organization, self.organization)

    def test_admin_sees_error_for_duplicated_email(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("members:create"), member_data(email="Ana@exemplo.com"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("email", response.context["form"].errors)
        self.assertEqual(Member.objects.filter(organization=self.organization).count(), 1)

    def test_admin_edits_member(self):
        self.client.force_login(self.admin)
        self.client.post(
            reverse("members:update", args=[self.member.pk]), member_data(name="Ana S.", email="ana@exemplo.com")
        )
        self.assertEqual(Member.objects.get(pk=self.member.pk).name, "Ana S.")

    def test_admin_deletes_member(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("members:delete", args=[self.member.pk]))
        self.assertRedirects(response, reverse("members:list"))
        self.assertFalse(Member.objects.filter(pk=self.member.pk).exists())


class MemberIsolationTests(MembersFixtureMixin, TestCase):
    def test_list_shows_only_own_organization_members(self):
        self.client.force_login(self.operator)
        response = self.client.get(reverse("members:list"))
        self.assertEqual(list(response.context["members"]), [self.member])
        self.assertNotContains(response, "Bruno Lima")

    def test_member_of_another_organization_is_not_found(self):
        self.client.force_login(self.admin)
        pk = self.other_member.pk
        self.assertEqual(self.client.get(reverse("members:detail", args=[pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("members:update", args=[pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("members:update", args=[pk]), member_data()).status_code, 404)
        self.assertEqual(self.client.post(reverse("members:delete", args=[pk])).status_code, 404)
        self.assertEqual(Member.objects.get(pk=pk).name, "Bruno Lima")
