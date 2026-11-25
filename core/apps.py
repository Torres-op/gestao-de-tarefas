from importlib import import_module

from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
    verbose_name = "Organizações e perfis"

    def ready(self):
        import_module(f"{self.name}.signals")
