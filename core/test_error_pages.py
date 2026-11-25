from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.views.defaults import server_error

from .testing import make_operator, make_organization, make_project


@override_settings(DEBUG=False)
class NotFoundPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.organization = make_organization("Org Erros")
        cls.operator = make_operator("operador.erros", cls.organization)
        cls.foreign_project = make_project(make_organization("Org Alheia"), "Projeto alheio")

    def assertFriendly404(self, response):
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "404.html")
        self.assertContains(response, "Página não encontrada", status_code=404)
        self.assertContains(response, "Página não encontrada &middot; Grello", status_code=404)
        self.assertContains(response, f'href="{reverse("home")}"', status_code=404)

    def test_unknown_url_uses_custom_template(self):
        self.client.force_login(self.operator)
        self.assertFriendly404(self.client.get("/rota-que-nao-existe/"))

    def test_unknown_url_for_anonymous_user(self):
        self.assertFriendly404(self.client.get("/rota-que-nao-existe/"))

    def test_object_from_other_organization_uses_custom_template(self):
        self.client.force_login(self.operator)
        response = self.client.get(reverse("projects:detail", args=[self.foreign_project.pk]))
        self.assertFriendly404(response)
        self.assertNotContains(response, "Projeto alheio", status_code=404)


class ServerErrorPageTests(TestCase):
    def test_renders_without_context(self):
        html = render_to_string("500.html")
        self.assertIn("<!doctype html>", html)
        self.assertIn("Erro interno &middot; Grello", html)
        self.assertIn("Algo deu errado", html)
        self.assertIn('href="/"', html)

    def test_default_handler_uses_template(self):
        response = server_error(RequestFactory().get("/"))
        self.assertEqual(response.status_code, 500)
        self.assertIn("Algo deu errado", response.content.decode())
