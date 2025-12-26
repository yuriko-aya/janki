from django import template

register = template.Library()


@register.filter(name='call_with')
def call_with(method, arg):
    """
    Template filter to call a method with a single argument.
    Usage: {% if team.is_admin|call_with:user %}
    """
    if callable(method):
        return method(arg)
    return False
