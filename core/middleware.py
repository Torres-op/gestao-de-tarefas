from django.shortcuts import render

from .tenancy import get_profile

EXEMPT_PREFIXES = ("/admin/", "/accounts/", "/api/", "/static/")


class OrganizationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.profile = get_profile(request.user)
        request.organization = request.profile.organization if request.profile else None

        needs_profile = request.user.is_authenticated and not request.path.startswith(EXEMPT_PREFIXES)
        if needs_profile and request.profile is None:
            return render(request, "core/no_profile.html", status=403)

        return self.get_response(request)
