from django import template
from megedc import __version__


register = template.Library()


@register.simple_tag
def megedc_version():
    return __version__
