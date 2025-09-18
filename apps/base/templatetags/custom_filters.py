import json

from django import template

from apps.clinic.models import Gender

# from apps.users.models import Gender

register = template.Library()


@register.filter
def get_gender_display(gender_value):
    if not gender_value:
        return ""
    for key, value in Gender.choices:
        if key == gender_value:
            return value


@register.filter
def format_date(date):
    if not date:
        return date
    return date.strftime("%d/%m/%Y")


@register.filter
def get_address_info(address, key):
    try:
        if not address:
            return ""
        address = json.loads(address) if isinstance(address, str) else address
        return address.get(key, "")
    except json.JSONDecodeError:
        return ""


@register.filter
def is_permission_granted(user_role, permitted_roles):
    """
    Check if the user has one of the roles specified in the permitted_roles.
    """
    permitted_roles = str(permitted_roles).split(", ")
    if user_role in permitted_roles:
        return True
    return False
