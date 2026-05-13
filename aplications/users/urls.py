from django.urls import path
from aplications.users import views

urlpatterns = [
    path(
        route='login/',
        view=views.login_view,
        name='login'
    ),

    path(
        route='logout/',
        view=views.logout_view,
        name='logout'
    ),

    path(
        route='signup/',
        view=views.signup,
        name='signup'
    ),

    path(
        route='update_profile/',
        view=views.update_profile,
        name='update_profile'
    ),

    path(
        route='panel_user/',
        view=views.user_panel,
        name='panel'
    ),

    path(
        route='',
        view=views.ping,
        name='ping'
    ),

    path(
        route='block/',
        view=views.block_user,
        name='block'
    ),

]
