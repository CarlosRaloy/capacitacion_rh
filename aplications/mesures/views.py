from decimal import Decimal, InvalidOperation
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import (
    KPICategory, KPIDefinition, KPIVariable, KPIVariableValue,
    EvaluationPeriod, PerformanceEvaluation, KPIMeasurement,
)
from .utils import safe_eval, extract_variable_names


def _resolve_category(raw_name: str):
    """
    Devuelve la KPICategory correspondiente al texto.
    - Si el texto está vacío → None.
    - Si ya existe (case-insensitive) → la reusa.
    - Si no existe → la crea con `name` tal cual lo escribió el usuario.
    """
    name = (raw_name or '').strip()
    if not name:
        return None
    existing = KPICategory.objects.filter(name__iexact=name).first()
    if existing:
        return existing
    return KPICategory.objects.create(name=name)


# ============================================================
#  Permisos
# ============================================================
MANAGER_LEVELS = {2, 3, 5}  # Administrador, Admin (sistema), RH


def _level(user) -> int:
    profile = getattr(user, 'profile', None)
    return getattr(profile, 'level', 0) or 0


def is_manager(user) -> bool:
    return _level(user) in MANAGER_LEVELS


def manager_required(view_func):
    """Solo Administrador / Admin sistema / RH pueden gestionar."""
    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if not is_manager(request.user):
            return HttpResponseForbidden("No tienes permisos para gestionar el módulo de desempeño.")
        return view_func(request, *args, **kwargs)
    return _wrapped


# ============================================================
#  Helpers
# ============================================================
def _to_decimal(value, default=Decimal('0')):
    try:
        if value in (None, ''):
            return default
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return default


def _to_int_or_none(value):
    try:
        return int(value) if value not in (None, '', 'None') else None
    except (TypeError, ValueError):
        return None


# ============================================================
#  Panel principal
# ============================================================
@login_required
def desempeno_main(request):
    """
    Lista de evaluaciones.
    - Managers (Admin / RH): ven todas.
    - Resto: ven solo las suyas (read-only).
    """
    qs = PerformanceEvaluation.objects.select_related(
        'employee', 'employee__profile', 'period', 'evaluator'
    )
    if not is_manager(request.user):
        qs = qs.filter(employee=request.user)

    period_id = _to_int_or_none(request.GET.get('period'))
    if period_id:
        qs = qs.filter(period_id=period_id)

    periods = EvaluationPeriod.objects.all()
    return render(request, 'mesures/desempeno_main.html', {
        'evaluations': qs,
        'periods': periods,
        'selected_period': period_id,
        'can_manage': is_manager(request.user),
    })


# ============================================================
#  Detalle (vista F-RH-10)
# ============================================================
@login_required
def evaluation_detail(request, pk):
    evaluation = get_object_or_404(
        PerformanceEvaluation.objects.select_related(
            'employee', 'employee__profile', 'employee__profile__position', 'employee__profile__area',
            'period', 'evaluator'
        ).prefetch_related('measurements__kpi'),
        pk=pk,
    )
    if not is_manager(request.user) and evaluation.employee_id != request.user.id:
        return HttpResponseForbidden("No puedes ver esta evaluación.")

    measurements = list(evaluation.measurements.all())
    return render(request, 'mesures/evaluation_detail.html', {
        'evaluation': evaluation,
        'measurements': measurements,
        'can_manage': is_manager(request.user),
    })


# ============================================================
#  Crear / Editar
# ============================================================
@manager_required
def evaluation_form(request, pk=None):
    """
    Vista única para crear/editar.
    - GET pk=None: form vacío con todos los KPIs activos.
    - GET pk=int: form con la evaluación cargada.
    - POST JSON: guarda employee/period/evaluator/notes + array measurements[].
    """
    evaluation = None
    if pk:
        evaluation = get_object_or_404(
            PerformanceEvaluation.objects.prefetch_related('measurements__kpi'),
            pk=pk,
        )

    if request.method == 'POST':
        try:
            employee_id = _to_int_or_none(request.POST.get('employee'))
            period_id = _to_int_or_none(request.POST.get('period'))
            evaluator_id = _to_int_or_none(request.POST.get('evaluator')) or request.user.id
            notes = (request.POST.get('notes') or '').strip()
            sign = request.POST.get('sign') == '1'

            if not employee_id or not period_id:
                return JsonResponse({'success': False, 'message': 'Trabajador y periodo son obligatorios.'})

            period = get_object_or_404(EvaluationPeriod, pk=period_id)
            if period.locked and not request.POST.get('force', ''):
                return JsonResponse({'success': False, 'message': f'El periodo {period} está bloqueado.'})

            if evaluation is None:
                evaluation, _ = PerformanceEvaluation.objects.get_or_create(
                    employee_id=employee_id, period_id=period_id,
                    defaults={'evaluator_id': evaluator_id, 'notes': notes},
                )
            evaluation.employee_id = employee_id
            evaluation.period_id = period_id
            evaluation.evaluator_id = evaluator_id
            evaluation.notes = notes or None
            if sign and not evaluation.signed_at:
                evaluation.signed_at = timezone.now()
            evaluation.save()

            # Mediciones — espera campos var_<kpi_id>_<var_id>_m1 / _m2
            existing = {m.kpi_id: m for m in evaluation.measurements.all()}
            for kpi in KPIDefinition.objects.filter(active=True).prefetch_related('variables'):
                # Detectar si vino algo de este KPI
                kpi_vars = list(kpi.variables.all())
                has_any = any(
                    request.POST.get(f'var_{kpi.id}_{v.id}_m1') is not None
                    or request.POST.get(f'var_{kpi.id}_{v.id}_m2') is not None
                    for v in kpi_vars
                )
                if not has_any:
                    continue

                meas = existing.get(kpi.id) or KPIMeasurement(evaluation=evaluation, kpi=kpi)
                meas.formula_snapshot = kpi.formula
                meas.ideal_percent_snapshot = kpi.ideal_percent
                meas.save()

                # Crear/actualizar valores por variable
                vv_existing = {vv.variable_id: vv for vv in meas.variable_values.all()}
                for v in kpi_vars:
                    m1 = _to_decimal(request.POST.get(f'var_{kpi.id}_{v.id}_m1'))
                    m2 = _to_decimal(request.POST.get(f'var_{kpi.id}_{v.id}_m2'))
                    vv = vv_existing.get(v.id) or KPIVariableValue(measurement=meas, variable=v)
                    vv.value_month1 = m1
                    vv.value_month2 = m2
                    vv.save()

            return JsonResponse({
                'success': True,
                'message': 'Evaluación guardada correctamente.',
                'redirect': reverse('mesures:evaluation_detail', args=[evaluation.id]),
            })
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Error al guardar: {e}'})

    # GET
    kpis = KPIDefinition.objects.filter(active=True).prefetch_related('variables')
    measurements_map = {}
    if evaluation:
        for m in evaluation.measurements.prefetch_related('variable_values__variable'):
            measurements_map[m.kpi_id] = {
                vv.variable_id: {'m1': vv.value_month1, 'm2': vv.value_month2}
                for vv in m.variable_values.all()
            }

    employees = User.objects.select_related('profile').filter(
        profile__level__gt=0
    ).order_by('first_name', 'last_name')
    periods = EvaluationPeriod.objects.all()
    return render(request, 'mesures/evaluation_form.html', {
        'evaluation': evaluation,
        'kpis': kpis,
        'measurements_map': measurements_map,
        'employees': employees,
        'periods': periods,
    })


@manager_required
@require_POST
def evaluation_delete(request, pk):
    evaluation = get_object_or_404(PerformanceEvaluation, pk=pk)
    evaluation.delete()
    return JsonResponse({'success': True, 'message': 'Evaluación eliminada.'})


# ============================================================
#  Catálogo de KPIs (con fórmula libre + variables dinámicas)
# ============================================================
def _validate_formula(formula: str, var_names: set):
    """
    Verifica que `formula` parsea, solo usa operadores aritméticos
    y que todos los nombres usados estén en `var_names ∪ {'ideal'}`.
    Levanta ValueError si algo no cuadra.
    """
    if not formula.strip():
        raise ValueError('La fórmula no puede estar vacía.')
    try:
        safe_eval(formula, {n: 1 for n in var_names} | {'ideal': 1})
    except ZeroDivisionError:
        # Una división por 1 no debería dar esto, pero por si acaso
        pass
    used = extract_variable_names(formula)
    allowed = set(var_names) | {'ideal'}
    unknown = used - allowed
    if unknown:
        raise ValueError(f"La fórmula usa variables no declaradas: {', '.join(sorted(unknown))}")


def _save_kpi_variables(kpi, payload_variables):
    """
    payload_variables: lista de dicts [{'name': 'obtenido', 'label': '...', 'order': 1}, ...]
    Reemplaza el conjunto completo de variables del KPI.
    """
    incoming_names = {v['name'] for v in payload_variables}
    # No permitir borrar variables usadas por mediciones (rompería el cálculo histórico)
    locked_var_ids = set(KPIVariableValue.objects.filter(
        variable__kpi=kpi
    ).exclude(variable__name__in=incoming_names).values_list('variable_id', flat=True))
    if locked_var_ids:
        locked_names = list(KPIVariable.objects.filter(id__in=locked_var_ids).values_list('name', flat=True))
        raise ValueError(f"No puedes eliminar variables con mediciones registradas: {', '.join(locked_names)}")

    existing = {v.name: v for v in kpi.variables.all()}
    for data in payload_variables:
        v = existing.get(data['name'])
        if v:
            v.label = data['label']
            v.save()
        else:
            KPIVariable.objects.create(kpi=kpi, name=data['name'], label=data['label'])
    # eliminar las que ya no vienen
    kpi.variables.exclude(name__in=incoming_names).delete()


def _parse_variables_from_post(request) -> list:
    """
    Acepta arrays `var_name[]`, `var_label[]`.
    Salta filas vacías. Slugifica el name. Valida unicidad y la palabra reservada `ideal`.
    """
    from django.utils.text import slugify
    names = request.POST.getlist('var_name[]')
    labels = request.POST.getlist('var_label[]')
    out = []
    seen = set()
    for i, raw_name in enumerate(names):
        slug = slugify(raw_name).replace('-', '_')
        if not slug:
            continue
        if slug == 'ideal':
            raise ValueError("'ideal' es una variable reservada. Usa otro nombre.")
        if slug in seen:
            raise ValueError(f"Variable duplicada: '{slug}'")
        seen.add(slug)
        label = (labels[i] if i < len(labels) else '').strip() or slug
        out.append({'name': slug, 'label': label})
    if not out:
        raise ValueError('Debe declarar al menos una variable.')
    return out


@manager_required
def panel_kpis(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        obj_id = request.POST.get('obj_id')

        if action in ('create', 'edit'):
            try:
                variables = _parse_variables_from_post(request)
                var_names = {v['name'] for v in variables}
                formula = (request.POST.get('formula') or '').strip()
                _validate_formula(formula, var_names)

                category = _resolve_category(request.POST.get('category_name'))
                if action == 'create':
                    kpi = KPIDefinition.objects.create(
                        name=request.POST['name'].strip(),
                        category=category,
                        formula=formula,
                        ideal_percent=_to_decimal(request.POST.get('ideal_percent')),
                        active=request.POST.get('active') in ('1', 'on', 'true', 'True'),
                    )
                else:
                    kpi = get_object_or_404(KPIDefinition, pk=obj_id)
                    kpi.name = request.POST['name'].strip()
                    kpi.category = category
                    kpi.formula = formula
                    kpi.ideal_percent = _to_decimal(request.POST.get('ideal_percent'))
                    kpi.active = request.POST.get('active') in ('1', 'on', 'true', 'True')
                    kpi.save()

                _save_kpi_variables(kpi, variables)
                msg = 'KPI creado.' if action == 'create' else 'KPI actualizado.'
                return JsonResponse({'success': True, 'message': msg})
            except ValueError as e:
                return JsonResponse({'success': False, 'message': str(e)})
            except Exception as e:
                return JsonResponse({'success': False, 'message': f'Error: {e}'})

        elif action == 'delete' and obj_id:
            try:
                kpi = get_object_or_404(KPIDefinition, pk=obj_id)
                if KPIMeasurement.objects.filter(kpi=kpi).exists():
                    kpi.active = False
                    kpi.save()
                    return JsonResponse({'success': True, 'message': 'KPI desactivado (tiene mediciones históricas).'})
                kpi.delete()
                return JsonResponse({'success': True, 'message': 'KPI eliminado.'})
            except Exception as e:
                return JsonResponse({'success': False, 'message': f'Error: {e}'})

        elif action == 'validate_formula':
            # Endpoint AJAX para probar la fórmula en vivo
            try:
                variables = _parse_variables_from_post(request)
                _validate_formula((request.POST.get('formula') or '').strip(), {v['name'] for v in variables})
                return JsonResponse({'success': True, 'message': '✓ Fórmula válida.'})
            except ValueError as e:
                return JsonResponse({'success': False, 'message': str(e)})

    kpis = KPIDefinition.objects.prefetch_related('variables').select_related('category').all()
    categories = KPICategory.objects.all()
    return render(request, 'mesures/panel_kpis.html', {'kpis': kpis, 'categories': categories})


# ============================================================
#  Catálogo de Periodos
# ============================================================
@manager_required
def panel_periods(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        obj_id = request.POST.get('obj_id')

        if action == 'create':
            try:
                EvaluationPeriod.objects.create(
                    year=int(request.POST['year']),
                    bimester=int(request.POST['bimester']),
                    notes=(request.POST.get('notes') or '').strip() or None,
                )
                return JsonResponse({'success': True, 'message': 'Periodo creado.'})
            except Exception as e:
                return JsonResponse({'success': False, 'message': f'Error: {e}'})

        elif action == 'edit' and obj_id:
            try:
                period = get_object_or_404(EvaluationPeriod, pk=obj_id)
                period.year = int(request.POST['year'])
                period.bimester = int(request.POST['bimester'])
                period.notes = (request.POST.get('notes') or '').strip() or None
                period.locked = request.POST.get('locked') in ('1', 'on', 'true', 'True')
                period.save()
                return JsonResponse({'success': True, 'message': 'Periodo actualizado.'})
            except Exception as e:
                return JsonResponse({'success': False, 'message': f'Error: {e}'})

        elif action == 'delete' and obj_id:
            try:
                period = get_object_or_404(EvaluationPeriod, pk=obj_id)
                if period.evaluations.exists():
                    return JsonResponse({'success': False, 'message': 'No se puede eliminar: el periodo tiene evaluaciones.'})
                period.delete()
                return JsonResponse({'success': True, 'message': 'Periodo eliminado.'})
            except Exception as e:
                return JsonResponse({'success': False, 'message': f'Error: {e}'})

    periods = EvaluationPeriod.objects.all()
    return render(request, 'mesures/panel_periods.html', {'periods': periods})
