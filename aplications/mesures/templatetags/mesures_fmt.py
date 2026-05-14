from django import template

register = template.Library()


@register.filter(name='kpi_display')
def kpi_display(value, kpi):
    """Formatea un valor con el prefijo/sufijo del KPI dado."""
    if kpi is None:
        return value
    return kpi.display(value)
