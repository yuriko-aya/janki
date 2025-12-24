from django import template
from calendar import month_name

register = template.Library()


@register.filter
def month_name_filter(month_num):
    """Convert month number (1-12) to month name."""
    try:
        return month_name[int(month_num)]
    except (ValueError, IndexError):
        return ""


@register.filter
def short_month_name(month_num):
    """Convert month number (1-12) to short month name (Jan, Feb, etc.)."""
    short_names = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    try:
        return short_names[int(month_num)]
    except (ValueError, IndexError):
        return ""


@register.filter(name='mul')
def multiply(value, arg):
    """Multiply the value by the argument."""
    try:
        return int(value) * int(arg)
    except (ValueError, TypeError):
        return 0
