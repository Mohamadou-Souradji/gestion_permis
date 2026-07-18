from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """Permet d'accéder à dict[key] depuis un template Django."""
    if dictionary is None:
        return None
    return dictionary.get(key)
