from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from aplications.users.forms import SignupForm, ProfileForm
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.urls import reverse
from .models import Profile

def _home_for(user) -> str:
    """
    Devuelve la URL absoluta (string) a la que debe ir el usuario
    según su nivel de perfil.
    """
    profile = getattr(user, "profile", None)
    level = getattr(profile, "level", 0)

    # Mapeo nivel -> nombre de url
    if level == 0:       # bloqueado
        url_name = "users:ping"
    elif level == 1:     # Usuario
        url_name = "users:ping"
    elif level == 2:     # Admin
        url_name = "users:ping"
    else:                # fallback
        url_name = "users:block"

    return reverse(url_name)

def login_view(request):
    registrado = request.GET.get('registrado') == '1'

    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            # redirección según nivel
            return redirect(_home_for(user))
        else:
            return render(request, 'users/login.html', {
                'error': 'El usuario o la contraseña son inválidos',
                'registrado': registrado
            })

    # GET
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
            # redirigimos con ?registrado=1
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

            # Actualiza theme
            profile.theme = data.get("theme") or profile.theme

            # No borres la foto si el usuario no subió una nueva
            new_picture = data.get("picture")
            if new_picture:
                profile.picture = new_picture

            profile.save()

            # Redirección correcta según nivel (admin y compras al panel)
            return redirect(_home_for(request.user))
    else:
        # Precarga theme actual para que el select salga con el valor actual
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
                Profile.objects.create(
                    user=user,
                    level=request.POST.get("level", 0),
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
                profile.level = request.POST.get("level", 0)
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

    users = User.objects.select_related("profile").all()
    return render(request, "users/user_panel.html", {"users": users})

@login_required
def ping(request):
    return render(request, 'blank.html', {'response': 'PONG (200)'})


def block_user(request):
    message = "Estas bloqueado por el momento, Espera que el administrador te desbloquee"
    return render(request, "block.html", {"message": message})
