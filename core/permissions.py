from functools import wraps

from django.core.exceptions import PermissionDenied

from .tenancy import current_organization, is_org_admin

ADMIN_ONLY_MESSAGE = "Somente administradores da organização podem realizar esta ação."


def admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not is_org_admin(request.user):
            raise PermissionDenied(ADMIN_ONLY_MESSAGE)
        return view_func(request, *args, **kwargs)

    return wrapper


class AdminRequiredMixin:
    def dispatch(self, request, *args, **kwargs):
        if not is_org_admin(request.user):
            raise PermissionDenied(ADMIN_ONLY_MESSAGE)
        return super().dispatch(request, *args, **kwargs)


class OrganizationScopedMixin:
    organization_field = "organization"

    def get_organization(self):
        return current_organization(self.request)

    def get_queryset(self):
        return super().get_queryset().filter(**{self.organization_field: self.get_organization()})


class OrganizationFormMixin:
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["organization"] = current_organization(self.request)
        return kwargs
