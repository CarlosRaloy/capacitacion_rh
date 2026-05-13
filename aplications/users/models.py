from django.contrib.auth.models import User
from django.db import models

"""
Levels
0 Bloqueado
1 Trabajador
3 Administrador
4 Jefes / Coordinadores / Lideres / Gerentes
5 RH 
"""

class PositionUserModel(models.Model):
    name_position = models.CharField(max_length = 100)
    description_position = models.TextField(blank=True, null=True)
    def __str__(self):
        return self.name_position

class AreasUserModel(models.Model):
    name_area = models.CharField(max_length = 100)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name_area

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    level = models.SmallIntegerField(default=0) # Nivel de usuario
    payroll_number = models.CharField(max_length=100, blank=True, null=True) # Numero de nomina
    position = models.ForeignKey(PositionUserModel, on_delete=models.SET_NULL, blank=True, null=True)
    area = models.ForeignKey(AreasUserModel, on_delete=models.SET_NULL, blank=True, null=True) # Departamentos
    boss = models.ForeignKey(
        User, on_delete=models.SET_NULL, blank=True, null=True,
        related_name='subordinates'
    ) # Jefe inmediato registrado en el sistema (level=4)
    boss_name = models.CharField(max_length=150, blank=True, null=True) # Jefe inmediato escrito a mano (fuera del sistema)
    signature = models.ImageField(upload_to='users/profile_signatures', blank=True, null=True)
    theme = models.CharField(max_length=15, default='default')
    picture = models.ImageField(upload_to='user/pictures', blank=True, null=True)
    tour = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.user.username
