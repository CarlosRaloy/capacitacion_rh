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
        name='panel_user'
    ),

    path(
        route='panel_positions/',
        view=views.panel_positions,
        name='panel_positions'
    ),

    path(
        route='panel_areas/',
        view=views.panel_areas,
        name='panel_areas'
    ),

    path(
        route='',
        view=views.ping,
        name='panel_main'
    ),

    path(
        route='block/',
        view=views.block_user,
        name='block'
    ),

]
