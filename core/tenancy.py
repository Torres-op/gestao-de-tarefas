from .models import Profile

PROFILE_RELATION = Profile._meta.get_field("user").remote_field


def load_profile(user):
    try:
        profile = Profile.objects.select_related("organization").get(user=user)
    except Profile.DoesNotExist:
        profile = None
    else:
        Profile._meta.get_field("user").set_cached_value(profile, user)
    PROFILE_RELATION.set_cached_value(user, profile)


def get_profile(user):
    if not user or not user.is_authenticated:
        return None
    if not PROFILE_RELATION.is_cached(user):
        load_profile(user)
    try:
        return user.profile
    except Profile.DoesNotExist:
        return None


def current_organization(request):
    return request.user.profile.organization


def is_org_admin(user):
    profile = get_profile(user)
    return bool(profile and profile.is_admin)
