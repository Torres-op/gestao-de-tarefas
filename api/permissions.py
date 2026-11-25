from rest_framework.permissions import SAFE_METHODS, BasePermission

from core.permissions import ADMIN_ONLY_MESSAGE
from core.tenancy import get_profile, is_org_admin


class HasOrganizationProfile(BasePermission):
    message = (
        "Seu usuário não está vinculado a nenhuma organização. "
        "Peça a um administrador para configurar o seu perfil."
    )

    def has_permission(self, request, view):
        return get_profile(request.user) is not None


class IsOrgAdminOrReadOnly(BasePermission):
    message = ADMIN_ONLY_MESSAGE

    def has_permission(self, request, view):
        return request.method in SAFE_METHODS or is_org_admin(request.user)


class IsOrgAdminToDelete(BasePermission):
    message = ADMIN_ONLY_MESSAGE

    def has_permission(self, request, view):
        return request.method != "DELETE" or is_org_admin(request.user)
