from django.urls import path
from aplications.mesures import views

urlpatterns = [
    path('', views.desempeno_main, name='desempeno_main'),

    path('evaluation/new/', views.evaluation_form, name='evaluation_create'),
    path('evaluation/<int:pk>/', views.evaluation_detail, name='evaluation_detail'),
    path('evaluation/<int:pk>/edit/', views.evaluation_form, name='evaluation_edit'),
    path('evaluation/<int:pk>/delete/', views.evaluation_delete, name='evaluation_delete'),

    path('kpis/', views.panel_kpis, name='panel_kpis'),
    path('periods/', views.panel_periods, name='panel_periods'),
]
