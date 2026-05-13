from django.contrib.auth.models import User
from django.db import models

"""
Areas
Levels
"""

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    level = models.SmallIntegerField(default=0)
    area = models.CharField(max_length=5,blank=True,null=True, default='NA')
    theme = models.CharField(max_length=15, default='default')
    picture = models.ImageField(upload_to='user/pictures', blank=True, null=True)
    tour = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.user.username
