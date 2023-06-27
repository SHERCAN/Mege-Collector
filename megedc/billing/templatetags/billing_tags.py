from django import template


register = template.Library()


@register.filter(name='get_form_field')
def get_form_field(value, attr, default=None):
    return value[attr]
