from .models import Profile


def get_profile(user):
    if not user or not user.is_authenticated:
        return None
    try:
        return user.profile
    except Profile.DoesNotExist:
        return None


def current_organization(request):
    return request.user.profile.organization


def is_org_admin(user):
    profile = get_profile(user)
    return bool(profile and profile.is_admin)
