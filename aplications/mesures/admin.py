from decimal import Decimal

from django.contrib import admin
from django.utils.html import format_html

from .models import (
    EvaluationPeriod,
    KPICategory,
    KPIDefinition,
    KPIMeasurement,
    KPIVariable,
    KPIVariableValue,
    PerformanceEvaluation,
)


# ----------------------------------------------------------------------
#  KPICategory
# ----------------------------------------------------------------------
@admin.register(KPICategory)
class KPICategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'kpi_count', 'active_kpi_count', 'created')
    search_fields = ('name',)
    ordering = ('name',)
    readonly_fields = ('created',)

    @admin.display(description='KPIs')
    def kpi_count(self, obj):
        return obj.kpis.count()

    @admin.display(description='KPIs activos')
    def active_kpi_count(self, obj):
        return obj.kpis.filter(active=True).count()


# ----------------------------------------------------------------------
#  KPIDefinition (+ variables en línea)
# ----------------------------------------------------------------------
class KPIVariableInline(admin.TabularInline):
    model = KPIVariable
    extra = 1
    fields = ('name',)
    verbose_name = 'Variable'
    verbose_name_plural = 'Variables (usables en la fórmula)'


@admin.register(KPIDefinition)
class KPIDefinitionAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'category', 'formula_short', 'ideal_display_col',
        'result_format', 'variables_summary', 'assigned_count',
        'active_badge', 'modified',
    )
    list_filter = ('active', 'result_format', 'category')
    search_fields = ('name', 'formula', 'category__name')
    autocomplete_fields = ('category', 'assigned_users')
    inlines = (KPIVariableInline,)
    readonly_fields = ('created', 'modified', 'variables_summary')
    fieldsets = (
        ('Definición', {
            'fields': ('name', 'category', 'active'),
        }),
        ('Cálculo', {
            'fields': ('formula', 'ideal_percent', 'result_format', 'variables_summary'),
            'description': (
                'Define las variables abajo y úsalas por nombre en la fórmula. '
                'La variable reservada <code>ideal</code> siempre está disponible.'
            ),
        }),
        ('Asignación de empleados', {
            'fields': ('assigned_users',),
            'description': 'Vacío = aplica a todos los empleados.',
        }),
        ('Auditoría', {
            'fields': ('created', 'modified'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description='Fórmula')
    def formula_short(self, obj):
        if not obj.formula:
            return '—'
        text = obj.formula
        return text if len(text) <= 45 else text[:42] + '…'

    @admin.display(description='Ideal')
    def ideal_display_col(self, obj):
        return obj.ideal_display

    @admin.display(description='Variables')
    def variables_summary(self, obj):
        names = list(obj.variables.values_list('name', flat=True))
        if not names:
            return format_html('<em style="color:#9ca3af;">sin variables</em>')
        return format_html(
            '<code style="background:#f3f4f6;padding:2px 6px;border-radius:4px;">{}</code>',
            ', '.join(names),
        )

    @admin.display(description='Asignados')
    def assigned_count(self, obj):
        count = obj.assigned_users.count()
        if count == 0:
            return format_html('<span style="color:#6b7280;">todos</span>')
        return count

    @admin.display(description='Estado', ordering='active')
    def active_badge(self, obj):
        if obj.active:
            return format_html(
                '<span style="background:#059669;color:#fff;padding:2px 8px;'
                'border-radius:999px;font-size:11px;">Activo</span>'
            )
        return format_html(
            '<span style="background:#9ca3af;color:#fff;padding:2px 8px;'
            'border-radius:999px;font-size:11px;">Inactivo</span>'
        )


# ----------------------------------------------------------------------
#  KPIVariable
# ----------------------------------------------------------------------
@admin.register(KPIVariable)
class KPIVariableAdmin(admin.ModelAdmin):
    list_display = ('kpi', 'name')
    list_filter = ('kpi__category', 'kpi')
    search_fields = ('name', 'kpi__name')
    autocomplete_fields = ('kpi',)
    ordering = ('kpi__name', 'name')


# ----------------------------------------------------------------------
#  EvaluationPeriod
# ----------------------------------------------------------------------
@admin.register(EvaluationPeriod)
class EvaluationPeriodAdmin(admin.ModelAdmin):
    list_display = (
        'year', 'bimester_label', 'months_label',
        'evaluation_count', 'locked_badge', 'modified',
    )
    list_filter = ('year', 'bimester', 'locked')
    search_fields = ('year', 'notes')
    ordering = ('-year', '-bimester')
    readonly_fields = ('created', 'modified')
    fieldsets = (
        ('Periodo', {
            'fields': ('year', 'bimester', 'locked'),
        }),
        ('Notas', {
            'fields': ('notes',),
        }),
        ('Auditoría', {
            'fields': ('created', 'modified'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description='Bimestre', ordering='bimester')
    def bimester_label(self, obj):
        return obj.get_bimester_display()

    @admin.display(description='Meses')
    def months_label(self, obj):
        m1, m2 = obj.month_labels
        return f'{m1} / {m2}'

    @admin.display(description='Evaluaciones')
    def evaluation_count(self, obj):
        return obj.evaluations.count()

    @admin.display(description='Estado', ordering='locked')
    def locked_badge(self, obj):
        if obj.locked:
            return format_html(
                '<span style="background:#dc2626;color:#fff;padding:2px 8px;'
                'border-radius:999px;font-size:11px;">Cerrado</span>'
            )
        return format_html(
            '<span style="background:#059669;color:#fff;padding:2px 8px;'
            'border-radius:999px;font-size:11px;">Abierto</span>'
        )


# ----------------------------------------------------------------------
#  PerformanceEvaluation (+ mediciones en línea)
# ----------------------------------------------------------------------
class KPIMeasurementInline(admin.TabularInline):
    model = KPIMeasurement
    extra = 0
    fields = ('kpi', 'ideal_percent_snapshot', 'formula_snapshot', 'bimester_result')
    readonly_fields = ('ideal_percent_snapshot', 'formula_snapshot', 'bimester_result')
    autocomplete_fields = ('kpi',)
    show_change_link = True
    verbose_name = 'KPI evaluado'
    verbose_name_plural = 'KPIs evaluados (clic en lápiz para capturar valores)'

    @admin.display(description='Resultado bimestre')
    def bimester_result(self, obj):
        if obj.pk is None:
            return '—'
        val = obj.percent_bimester
        if val is None:
            return '—'
        return obj.kpi.display(val)


@admin.register(PerformanceEvaluation)
class PerformanceEvaluationAdmin(admin.ModelAdmin):
    list_display = (
        'employee_display', 'period', 'evaluator_display',
        'overall_display', 'measurement_count', 'signed_at',
    )
    list_filter = ('period__year', 'period__bimester', 'period__locked')
    search_fields = (
        'employee__username', 'employee__first_name', 'employee__last_name',
        'evaluator__username', 'evaluator__first_name', 'evaluator__last_name',
        'notes',
    )
    autocomplete_fields = ('employee', 'period', 'evaluator')
    readonly_fields = ('overall_display', 'created', 'modified')
    inlines = (KPIMeasurementInline,)
    list_select_related = ('employee', 'period', 'evaluator')
    fieldsets = (
        ('Evaluación', {
            'fields': ('employee', 'period', 'evaluator', 'signed_at'),
        }),
        ('Resultado', {
            'fields': ('overall_display',),
        }),
        ('Notas', {
            'fields': ('notes',),
        }),
        ('Auditoría', {
            'fields': ('created', 'modified'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description='Empleado', ordering='employee__first_name')
    def employee_display(self, obj):
        return obj.employee.get_full_name() or obj.employee.username

    @admin.display(description='Evaluador', ordering='evaluator__first_name')
    def evaluator_display(self, obj):
        if not obj.evaluator:
            return '—'
        return obj.evaluator.get_full_name() or obj.evaluator.username

    @admin.display(description='Resultado bimestre')
    def overall_display(self, obj):
        try:
            val = obj.overall_percent
        except Exception:
            return '—'
        if val is None:
            return '—'
        color = '#059669' if val >= Decimal('80') else '#dc2626' if val < Decimal('60') else '#ea580c'
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 10px;'
            'border-radius:999px;font-size:12px;font-weight:600;">{}%</span>',
            color, val,
        )

    @admin.display(description='KPIs')
    def measurement_count(self, obj):
        return obj.measurements.count()


# ----------------------------------------------------------------------
#  KPIMeasurement (+ valores en línea)
# ----------------------------------------------------------------------
class KPIVariableValueInline(admin.TabularInline):
    model = KPIVariableValue
    extra = 0
    autocomplete_fields = ('variable',)
    verbose_name = 'Captura por variable'
    verbose_name_plural = 'Valores capturados por variable (mes 1 / mes 2)'


@admin.register(KPIMeasurement)
class KPIMeasurementAdmin(admin.ModelAdmin):
    list_display = (
        'kpi', 'evaluation_employee', 'evaluation_period',
        'month1_display', 'month2_display', 'bimester_display',
        'objective_badge',
    )
    list_filter = (
        'kpi', 'kpi__category',
        'evaluation__period__year', 'evaluation__period__bimester',
    )
    search_fields = (
        'kpi__name',
        'evaluation__employee__username',
        'evaluation__employee__first_name',
        'evaluation__employee__last_name',
    )
    autocomplete_fields = ('evaluation', 'kpi')
    readonly_fields = (
        'formula_snapshot', 'ideal_percent_snapshot',
        'month1_display', 'month2_display', 'bimester_display',
    )
    inlines = (KPIVariableValueInline,)
    list_select_related = ('kpi', 'evaluation', 'evaluation__employee', 'evaluation__period')
    fieldsets = (
        ('KPI evaluado', {
            'fields': ('evaluation', 'kpi'),
        }),
        ('Snapshot al momento de capturar', {
            'fields': ('formula_snapshot', 'ideal_percent_snapshot'),
            'description': (
                'Se rellena automáticamente al guardar; congela la fórmula y el ideal '
                'para preservar el histórico aunque el KPI cambie.'
            ),
        }),
        ('Resultados calculados', {
            'fields': ('month1_display', 'month2_display', 'bimester_display'),
        }),
    )

    @admin.display(description='Empleado', ordering='evaluation__employee__first_name')
    def evaluation_employee(self, obj):
        emp = obj.evaluation.employee
        return emp.get_full_name() or emp.username

    @admin.display(description='Periodo', ordering='evaluation__period__year')
    def evaluation_period(self, obj):
        return str(obj.evaluation.period)

    @admin.display(description='Mes 1')
    def month1_display(self, obj):
        return obj.kpi.display(obj.percent_month1)

    @admin.display(description='Mes 2')
    def month2_display(self, obj):
        return obj.kpi.display(obj.percent_month2)

    @admin.display(description='Bimestre')
    def bimester_display(self, obj):
        return obj.kpi.display(obj.percent_bimester)

    @admin.display(description='Objetivo')
    def objective_badge(self, obj):
        info = obj.comparison_badge
        if not info:
            return '—'
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:999px;font-size:11px;">{} {}</span>',
            info['color'], info['icon'], info['text'],
        )


# ----------------------------------------------------------------------
#  KPIVariableValue (vista directa para correcciones puntuales)
# ----------------------------------------------------------------------
@admin.register(KPIVariableValue)
class KPIVariableValueAdmin(admin.ModelAdmin):
    list_display = (
        'measurement_kpi', 'measurement_employee', 'measurement_period',
        'variable', 'value_month1', 'value_month2',
    )
    list_filter = (
        'variable__kpi',
        'measurement__evaluation__period__year',
        'measurement__evaluation__period__bimester',
    )
    search_fields = (
        'variable__name',
        'measurement__kpi__name',
        'measurement__evaluation__employee__username',
        'measurement__evaluation__employee__first_name',
        'measurement__evaluation__employee__last_name',
    )
    autocomplete_fields = ('measurement', 'variable')
    list_select_related = (
        'variable', 'measurement', 'measurement__kpi',
        'measurement__evaluation', 'measurement__evaluation__employee',
        'measurement__evaluation__period',
    )

    @admin.display(description='KPI', ordering='measurement__kpi__name')
    def measurement_kpi(self, obj):
        return obj.measurement.kpi.name

    @admin.display(description='Empleado')
    def measurement_employee(self, obj):
        emp = obj.measurement.evaluation.employee
        return emp.get_full_name() or emp.username

    @admin.display(description='Periodo')
    def measurement_period(self, obj):
        return str(obj.measurement.evaluation.period)
