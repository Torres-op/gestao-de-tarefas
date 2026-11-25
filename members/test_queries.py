from django.test import TestCase
from django.urls import reverse

from core.testing import QueryCountScenario


class MemberQueryCountTests(QueryCountScenario, TestCase):
    def test_member_list(self):
        self.assertQueriesStayAt(4, reverse("members:list"))

    def test_member_detail(self):
        self.assertQueriesStayAt(7, reverse("members:detail", args=[self.member.pk]))

    def test_member_detail_as_operator(self):
        self.assertQueriesStayAt(7, reverse("members:detail", args=[self.member.pk]), user=self.operator)

    def test_member_create_form(self):
        self.assertQueriesStayAt(3, reverse("members:create"))

    def test_member_update_form(self):
        self.assertQueriesStayAt(4, reverse("members:update", args=[self.member.pk]))

    def test_member_delete_confirmation(self):
        self.assertQueriesStayAt(4, reverse("members:delete", args=[self.member.pk]))
