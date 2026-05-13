from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from aplications.users.forms import SignupForm, ProfileForm
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.urls import reverse
from .models import Profile, PositionUserModel, AreasUserModel


def _home_for(user) -> str:
    """
    Devuelve la URL absoluta (string) a la que debe ir el usuario
    según su nivel de perfil.
    """
    profile = getattr(user, "profile", None)
    level = getattr(profile, "level", 0)

    # Mapeo nivel -> nombre de url
    if level == 0:       # bloqueado
        url_name = "users:block"
    elif level == 1:     # Usuario
        url_name = "users:panel_main"
    elif level == 2:     # Admin
        url_name = "users:panel_main"
    else:                # fallback
        url_name = "users:block"

    return reverse(url_name)


def _to_int_or_none(value):
    try:
        return int(value) if value not in (None, "", "None") else None
    except (TypeError, ValueError):
        return None


def login_view(request):
    registrado = request.GET.get('registrado') == '1'

    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect(_home_for(user))
        else:
            return render(request, 'users/login.html', {
                'error': 'El usuario o la contraseña son inválidos',
                'registrado': registrado
            })

    return render(request, 'users/login.html', {
        'registrado': registrado
    })


@login_required
def logout_view(request):
    logout(request)
    return redirect('users:login')


def signup(request):
    if request.method == 'POST':
        form = SignupForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect(f"{reverse('users:login')}?registrado=1")
    else:
        form = SignupForm()

    return render(request, 'users/signup.html', {
        'form': form
    })


@login_required
def update_profile(request):
    profile = request.user.profile

    if request.method == "POST":
        form = ProfileForm(request.POST, request.FILES)
        if form.is_valid():
            data = form.cleaned_data
            profile.theme = data.get("theme") or profile.theme
            new_picture = data.get("picture")
            if new_picture:
                profile.picture = new_picture
            profile.save()
            return redirect(_home_for(request.user))
    else:
        form = ProfileForm(initial={"theme": getattr(profile, "theme", "")})

    return render(
        request,
        "users/update_profile.html",
        {
            "profile": profile,
            "user": request.user,
            "form": form,
        },
    )


@login_required
def user_panel(request):
    if request.method == "POST":
        action = request.POST.get("action")
        user_id = request.POST.get("user_id")

        if action == "create":
            try:
                user = User.objects.create_user(
                    username=request.POST["username"],
                    password=request.POST["password"],
                    first_name=request.POST["first_name"],
                    last_name=request.POST["last_name"],
                    email=request.POST.get("email", "").strip()
                )
                boss_mode = request.POST.get("boss_mode", "list")
                boss_id = _to_int_or_none(request.POST.get("boss")) if boss_mode == "list" else None
                boss_name = request.POST.get("boss_name", "").strip() or None if boss_mode == "manual" else None
                Profile.objects.create(
                    user=user,
                    level=_to_int_or_none(request.POST.get("level")) or 0,
                    payroll_number=request.POST.get("payroll_number", "").strip() or None,
                    position_id=_to_int_or_none(request.POST.get("position")),
                    area_id=_to_int_or_none(request.POST.get("area")),
                    boss_id=boss_id,
                    boss_name=boss_name,
                )
                return JsonResponse({"success": True, "message": "Usuario creado exitosamente."})
            except Exception as e:
                return JsonResponse({"success": False, "message": f"Error al crear usuario: {str(e)}"})

        elif action == "edit" and user_id:
            try:
                user = get_object_or_404(User, pk=user_id)
                user.first_name = request.POST["first_name"]
                user.last_name = request.POST["last_name"]
                user.email = request.POST.get("email", "").strip()
                user.save()
                profile = user.profile
                profile.level = _to_int_or_none(request.POST.get("level")) or 0
                profile.payroll_number = request.POST.get("payroll_number", "").strip() or None
                profile.position_id = _to_int_or_none(request.POST.get("position"))
                profile.area_id = _to_int_or_none(request.POST.get("area"))
                boss_mode = request.POST.get("boss_mode", "list")
                if boss_mode == "manual":
                    profile.boss_id = None
                    profile.boss_name = request.POST.get("boss_name", "").strip() or None
                else:
                    profile.boss_id = _to_int_or_none(request.POST.get("boss"))
                    profile.boss_name = None
                # Evita ciclo: un usuario no puede ser su propio jefe
                if profile.boss_id == user.id:
                    profile.boss_id = None
                profile.save()
                return JsonResponse({"success": True, "message": "Usuario actualizado correctamente."})
            except Exception as e:
                return JsonResponse({"success": False, "message": f"Error al editar usuario: {str(e)}"})

        elif action == "delete" and user_id:
            try:
                user = get_object_or_404(User, pk=user_id)
                user.delete()
                return JsonResponse({"success": True, "message": "Usuario eliminado correctamente."})
            except Exception as e:
                return JsonResponse({"success": False, "message": f"Error al eliminar usuario: {str(e)}"})

    users = User.objects.select_related(
        "profile", "profile__position", "profile__area", "profile__boss"
    ).all()
    positions = PositionUserModel.objects.all().order_by("name_position")
    areas = AreasUserModel.objects.all().order_by("name_area")
    bosses = User.objects.select_related("profile").filter(profile__level=4).order_by("first_name", "last_name")
    return render(request, "users/user_panel.html", {
        "users": users,
        "positions": positions,
        "areas": areas,
        "bosses": bosses,
    })


@login_required
def panel_positions(request):
    if request.method == "POST":
        action = request.POST.get("action")
        obj_id = request.POST.get("obj_id")

        if action == "create":
            try:
                PositionUserModel.objects.create(
                    name_position=request.POST["name_position"].strip(),
                    description_position=request.POST.get("description_position", "").strip() or None,
                )
                return JsonResponse({"success": True, "message": "Puesto creado correctamente."})
            except Exception as e:
                return JsonResponse({"success": False, "message": f"Error al crear puesto: {str(e)}"})

        elif action == "edit" and obj_id:
            try:
                pos = get_object_or_404(PositionUserModel, pk=obj_id)
                pos.name_position = request.POST["name_position"].strip()
                pos.description_position = request.POST.get("description_position", "").strip() or None
                pos.save()
                return JsonResponse({"success": True, "message": "Puesto actualizado."})
            except Exception as e:
                return JsonResponse({"success": False, "message": f"Error al editar puesto: {str(e)}"})

        elif action == "delete" and obj_id:
            try:
                pos = get_object_or_404(PositionUserModel, pk=obj_id)
                pos.delete()
                return JsonResponse({"success": True, "message": "Puesto eliminado."})
            except Exception as e:
                return JsonResponse({"success": False, "message": f"Error al eliminar puesto: {str(e)}"})

    positions = PositionUserModel.objects.all().order_by("name_position")
    return render(request, "users/panel_positions.html", {"positions": positions})


@login_required
def panel_areas(request):
    if request.method == "POST":
        action = request.POST.get("action")
        obj_id = request.POST.get("obj_id")

        if action == "create":
            try:
                AreasUserModel.objects.create(
                    name_area=request.POST["name_area"].strip(),
                    description=request.POST.get("description", "").strip() or None,
                )
                return JsonResponse({"success": True, "message": "Área creada correctamente."})
            except Exception as e:
                return JsonResponse({"success": False, "message": f"Error al crear área: {str(e)}"})

        elif action == "edit" and obj_id:
            try:
                area = get_object_or_404(AreasUserModel, pk=obj_id)
                area.name_area = request.POST["name_area"].strip()
                area.description = request.POST.get("description", "").strip() or None
                area.save()
                return JsonResponse({"success": True, "message": "Área actualizada."})
            except Exception as e:
                return JsonResponse({"success": False, "message": f"Error al editar área: {str(e)}"})

        elif action == "delete" and obj_id:
            try:
                area = get_object_or_404(AreasUserModel, pk=obj_id)
                area.delete()
                return JsonResponse({"success": True, "message": "Área eliminada."})
            except Exception as e:
                return JsonResponse({"success": False, "message": f"Error al eliminar área: {str(e)}"})

    areas = AreasUserModel.objects.all().order_by("name_area")
    return render(request, "users/panel_areas.html", {"areas": areas})


@login_required
def ping(request):
    return render(request, 'blank.html', {'response': 'PONG (200)'})


def block_user(request):
    message = "Estas bloqueado por el momento, Espera que el administrador te desbloquee"
    return render(request, "block.html", {"message": message})
