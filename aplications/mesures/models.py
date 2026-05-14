from decimal import Decimal
from django.contrib.auth.models import User
from django.db import models

from .utils import safe_eval


class KPICategory(models.Model):
    """Categoría editable para agrupar KPIs."""
    name = models.CharField(max_length=120, unique=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'KPI categories'

    def __str__(self):
        return self.name


class KPIDefinition(models.Model):
    """
    Catálogo editable de indicadores con fórmula libre.

    El admin define:
      - N variables (KPIVariable) con `name` (usable en la fórmula) y `label`.
      - Una `formula` en sintaxis aritmética. La variable reservada `ideal`
        siempre está disponible y representa `ideal_percent`.

    Ejemplo: variables = [obtenido, esperado]; formula = "obtenido / esperado * ideal".
    """

    name = models.CharField(max_length=120)
    category = models.ForeignKey(
        KPICategory, on_delete=models.SET_NULL, blank=True, null=True, related_name='kpis'
    )
    formula = models.CharField(
        max_length=500, default='',
        help_text='Expresión aritmética. Variables disponibles: las definidas + `ideal`.'
    )
    ideal_percent = models.DecimalField(
        max_digits=5, decimal_places=2,
        help_text='% ideal del KPI (también accesible en la fórmula como `ideal`).'
    )
    active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return self.name


class KPIVariable(models.Model):
    """Variable que se captura por mes en cada evaluación."""
    kpi = models.ForeignKey(KPIDefinition, on_delete=models.CASCADE, related_name='variables')
    name = models.SlugField(
        max_length=40,
        help_text='Identificador usado en la fórmula (sin espacios, ej. "obtenido").'
    )
    label = models.CharField(max_length=120, help_text='Etiqueta visible (ej. "Resultado Obtenido").')

    class Meta:
        unique_together = ('kpi', 'name')
        ordering = ['id']

    def __str__(self):
        return f"{self.kpi.name}.{self.name}"


class EvaluationPeriod(models.Model):
    BIMESTER_CHOICES = (
        (1, 'Ene-Feb'),
        (2, 'Mar-Abr'),
        (3, 'May-Jun'),
        (4, 'Jul-Ago'),
        (5, 'Sep-Oct'),
        (6, 'Nov-Dic'),
    )
    MONTHS_BY_BIMESTER = {
        1: ('Enero', 'Febrero'),
        2: ('Marzo', 'Abril'),
        3: ('Mayo', 'Junio'),
        4: ('Julio', 'Agosto'),
        5: ('Septiembre', 'Octubre'),
        6: ('Noviembre', 'Diciembre'),
    }

    year = models.PositiveIntegerField()
    bimester = models.PositiveSmallIntegerField(choices=BIMESTER_CHOICES)
    locked = models.BooleanField(default=False)
    notes = models.TextField(blank=True, null=True)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('year', 'bimester')
        ordering = ['-year', '-bimester']

    def __str__(self):
        return f"{self.year} · {self.get_bimester_display()}"

    @property
    def month_labels(self):
        return self.MONTHS_BY_BIMESTER.get(self.bimester, ('Mes 1', 'Mes 2'))


class PerformanceEvaluation(models.Model):
    employee = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='performance_evaluations'
    )
    period = models.ForeignKey(EvaluationPeriod, on_delete=models.PROTECT, related_name='evaluations')
    evaluator = models.ForeignKey(
        User, on_delete=models.SET_NULL, blank=True, null=True, related_name='evaluations_made'
    )
    signed_at = models.DateTimeField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('employee', 'period')
        ordering = ['-period__year', '-period__bimester', 'employee__first_name']

    def __str__(self):
        return f"{self.employee.get_full_name() or self.employee.username} — {self.period}"

    @property
    def overall_percent(self):
        values = [m.percent_bimester for m in self.measurements.all() if m.percent_bimester is not None]
        if not values:
            return Decimal('0')
        return (sum(values) / len(values)).quantize(Decimal('0.01'))


class KPIMeasurement(models.Model):
    """
    Fila de KPI dentro de una evaluación.

    Los valores se guardan en KPIVariableValue (uno por variable, con valor mes1/mes2).
    `formula_snapshot` y `ideal_percent_snapshot` congelan la definición al momento de capturar
    para que cambios futuros al KPI no alteren el histórico.
    """
    evaluation = models.ForeignKey(
        PerformanceEvaluation, on_delete=models.CASCADE, related_name='measurements'
    )
    kpi = models.ForeignKey(KPIDefinition, on_delete=models.PROTECT)
    formula_snapshot = models.CharField(max_length=500)
    ideal_percent_snapshot = models.DecimalField(max_digits=5, decimal_places=2)

    class Meta:
        unique_together = ('evaluation', 'kpi')
        ordering = ['kpi__id']

    def __str__(self):
        return f"{self.kpi.name} ({self.evaluation})"

    def save(self, *args, **kwargs):
        if self.kpi_id:
            if not self.formula_snapshot:
                self.formula_snapshot = self.kpi.formula
            if not self.ideal_percent_snapshot:
                self.ideal_percent_snapshot = self.kpi.ideal_percent
        super().save(*args, **kwargs)

    # ----------------------------------------------------------------
    #  Cálculo
    # ----------------------------------------------------------------
    def _values_for(self, month: int) -> dict:
        """Devuelve dict {variable_name: Decimal} para el mes (1 o 2). `ideal` siempre incluido."""
        ctx = {'ideal': Decimal(self.ideal_percent_snapshot)}
        for vv in self.variable_values.select_related('variable'):
            ctx[vv.variable.name] = Decimal(vv.value_month1 if month == 1 else vv.value_month2)
        return ctx

    def _evaluate_for(self, month: int):
        try:
            result = safe_eval(self.formula_snapshot, self._values_for(month))
            return Decimal(result).quantize(Decimal('0.01'))
        except (ZeroDivisionError, ValueError, ArithmeticError):
            return None

    @property
    def percent_month1(self):
        return self._evaluate_for(1)

    @property
    def percent_month2(self):
        return self._evaluate_for(2)

    @property
    def percent_bimester(self):
        m1, m2 = self.percent_month1, self.percent_month2
        if m1 is None and m2 is None:
            return None
        if m1 is None:
            return m2
        if m2 is None:
            return m1
        return ((m1 + m2) / 2).quantize(Decimal('0.01'))


class KPIVariableValue(models.Model):
    """Valor capturado por mes para una variable de una medición."""
    measurement = models.ForeignKey(
        KPIMeasurement, on_delete=models.CASCADE, related_name='variable_values'
    )
    variable = models.ForeignKey(KPIVariable, on_delete=models.PROTECT)
    value_month1 = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal('0'))
    value_month2 = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal('0'))

    class Meta:
        unique_together = ('measurement', 'variable')

    def __str__(self):
        return f"{self.variable.name} → {self.value_month1} / {self.value_month2}"
