# users/forms.py
from django import forms
from django.contrib.auth.models import User
from aplications.users.models import Profile

class SignupForm(forms.Form):
    username = forms.CharField(
        min_length=4, max_length=50,
        widget=forms.TextInput(attrs={
            'class':'form-control',
            'placeholder':'Usuario'
        })
    )
    password = forms.CharField(
        max_length=70,
        widget=forms.PasswordInput(attrs={
            'class':'form-control',
            'placeholder':'Contraseña'
        })
    )
    password_confirmation = forms.CharField(
        max_length=70,
        widget=forms.PasswordInput(attrs={
            'class':'form-control',
            'placeholder':'Confirmar contraseña'
        })
    )

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("Este nombre de usuario ya está en uso.")
        return username

    def clean(self):
        data = super().clean()
        pwd = data.get('password')
        pwd2 = data.get('password_confirmation')
        if pwd and pwd2 and pwd != pwd2:
            raise forms.ValidationError("Las contraseñas no coinciden.")
        return data

    def save(self):
        data = self.cleaned_data
        data.pop('password_confirmation')
        user = User.objects.create_user(
            username=data['username'],
            password=data['password']
        )
        Profile.objects.create(user=user)
        return user



# Actualizar Perfil

themes ={
    ('apple', 'apple'),
    ('default', 'default'),
    ('facebook', 'facebook'),
    ('material', 'material'),
    ('transparent', 'transparent'),
    ('google', 'google'),
}


class ProfileForm(forms.Form):
    """Profile form."""
    theme = forms.CharField(widget=forms.Select(choices=themes))
    picture = forms.ImageField(required=False)