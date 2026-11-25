def organization(request):
    profile = getattr(request, "profile", None)
    return {
        "current_profile": profile,
        "current_organization": profile.organization if profile else None,
        "is_org_admin": bool(profile and profile.is_admin),
    }
