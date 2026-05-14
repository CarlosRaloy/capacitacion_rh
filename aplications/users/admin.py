from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html

from .models import AreasUserModel, PositionUserModel, Profile


admin.site.site_header = 'Raloy · Panel de administración'
admin.site.site_title = 'Raloy Admin'
admin.site.index_title = 'Soporte y configuración'


LEVEL_LABELS = {
    0: 'Bloqueado',
    1: 'Trabajador',
    2: 'Administrador',
    3: 'Administrador',
    4: 'Jefe / Líder',
    5: 'Recursos Humanos',
}

LEVEL_COLORS = {
    0: '#dc2626',
    1: '#2563eb',
    2: '#7c3aed',
    3: '#7c3aed',
    4: '#ea580c',
    5: '#059669',
}


def _truncate(text, limit=60):
    if not text:
        return '—'
    return text if len(text) <= limit else text[: limit - 1] + '…'


@admin.register(PositionUserModel)
class PositionUserAdmin(admin.ModelAdmin):
    list_display = ('name_position', 'short_description', 'people_count')
    search_fields = ('name_position', 'description_position')
    ordering = ('name_position',)

    @admin.display(description='Descripción')
    def short_description(self, obj):
        return _truncate(obj.description_position)

    @admin.display(description='Personas')
    def people_count(self, obj):
        return Profile.objects.filter(position=obj).count()


@admin.register(AreasUserModel)
class AreasUserAdmin(admin.ModelAdmin):
    list_display = ('name_area', 'short_description', 'people_count')
    search_fields = ('name_area', 'description')
    ordering = ('name_area',)

    @admin.display(description='Descripción')
    def short_description(self, obj):
        return _truncate(obj.description)

    @admin.display(description='Personas')
    def people_count(self, obj):
        return Profile.objects.filter(area=obj).count()


class ProfileInline(admin.StackedInline):
    """Perfil mostrado en la pantalla del usuario para edición rápida."""
    model = Profile
    can_delete = False
    fk_name = 'user'
    extra = 0
    verbose_name = 'Perfil'
    verbose_name_plural = 'Perfil'
    autocomplete_fields = ('position', 'area', 'boss')
    readonly_fields = ('created', 'modified', 'picture_preview', 'signature_preview')
    fieldsets = (
        ('Acceso', {
            'fields': ('level', 'tour'),
            'description': '0 Bloqueado · 1 Trabajador · 2/3 Administrador · 4 Jefe/Líder · 5 RH',
        }),
        ('Datos laborales', {
            'fields': ('payroll_number', 'position', 'area', 'boss', 'boss_name'),
        }),
        ('Imágenes', {
            'fields': ('picture', 'picture_preview', 'signature', 'signature_preview'),
        }),
        ('Apariencia', {
            'fields': ('theme',),
            'classes': ('collapse',),
        }),
        ('Auditoría', {
            'fields': ('created', 'modified'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description='Vista previa foto')
    def picture_preview(self, obj):
        if obj and obj.picture:
            return format_html(
                '<img src="{}" style="max-height:120px;border-radius:6px;border:1px solid #ddd;">',
                obj.picture.url,
            )
        return '—'

    @admin.display(description='Vista previa firma')
    def signature_preview(self, obj):
        if obj and obj.signature:
            return format_html(
                '<img src="{}" style="max-height:80px;background:#fff;border:1px solid #ddd;padding:4px;">',
                obj.signature.url,
            )
        return '—'


class CustomUserAdmin(BaseUserAdmin):
    """User admin extendido con el perfil Raloy en línea."""
    inlines = (ProfileInline,)
    list_display = (
        'username', 'full_name', 'email',
        'level_badge', 'area_display', 'position_display',
        'is_active', 'last_login',
    )
    list_filter = (
        'is_active', 'is_staff',
        'profile__level', 'profile__area', 'profile__position',
    )
    search_fields = (
        'username', 'first_name', 'last_name', 'email',
        'profile__payroll_number', 'profile__boss_name',
    )
    list_select_related = ('profile', 'profile__area', 'profile__position')
    ordering = ('username',)

    @admin.display(description='Nombre', ordering='first_name')
    def full_name(self, obj):
        return obj.get_full_name() or '—'

    @admin.display(description='Nivel', ordering='profile__level')
    def level_badge(self, obj):
        prof = getattr(obj, 'profile', None)
        if prof is None:
            return format_html(
                '<span style="color:#9ca3af;font-style:italic;">sin perfil</span>'
            )
        label = LEVEL_LABELS.get(prof.level, f'Nivel {prof.level}')
        color = LEVEL_COLORS.get(prof.level, '#6b7280')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:999px;font-size:11px;white-space:nowrap;">{} · {}</span>',
            color, prof.level, label,
        )

    @admin.display(description='Área', ordering='profile__area__name_area')
    def area_display(self, obj):
        prof = getattr(obj, 'profile', None)
        return prof.area.name_area if prof and prof.area else '—'

    @admin.display(description='Puesto', ordering='profile__position__name_position')
    def position_display(self, obj):
        prof = getattr(obj, 'profile', None)
        return prof.position.name_position if prof and prof.position else '—'


admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    """Vista directa de perfiles para búsquedas y filtrado masivo."""
    list_display = (
        'user', 'full_name', 'level_label',
        'payroll_number', 'position', 'area', 'boss_display', 'modified',
    )
    list_filter = ('level', 'area', 'position', 'theme')
    search_fields = (
        'user__username', 'user__first_name', 'user__last_name', 'user__email',
        'payroll_number', 'boss_name',
    )
    autocomplete_fields = ('user', 'position', 'area', 'boss')
    readonly_fields = ('created', 'modified', 'picture_preview', 'signature_preview')
    list_select_related = ('user', 'position', 'area', 'boss')
    fieldsets = (
        ('Usuario', {
            'fields': ('user', 'level', 'tour'),
        }),
        ('Datos laborales', {
            'fields': ('payroll_number', 'position', 'area', 'boss', 'boss_name'),
        }),
        ('Imágenes', {
            'fields': ('picture', 'picture_preview', 'signature', 'signature_preview'),
        }),
        ('Apariencia', {
            'fields': ('theme',),
        }),
        ('Auditoría', {
            'fields': ('created', 'modified'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description='Nombre', ordering='user__first_name')
    def full_name(self, obj):
        return obj.user.get_full_name() or '—'

    @admin.display(description='Nivel', ordering='level')
    def level_label(self, obj):
        color = LEVEL_COLORS.get(obj.level, '#6b7280')
        label = LEVEL_LABELS.get(obj.level, 'Desconocido')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:999px;font-size:11px;">{} · {}</span>',
            color, obj.level, label,
        )

    @admin.display(description='Jefe inmediato')
    def boss_display(self, obj):
        if obj.boss:
            return obj.boss.get_full_name() or obj.boss.username
        return obj.boss_name or '—'

    @admin.display(description='Vista previa foto')
    def picture_preview(self, obj):
        if obj.picture:
            return format_html(
                '<img src="{}" style="max-height:120px;border-radius:6px;border:1px solid #ddd;">',
                obj.picture.url,
            )
        return '—'

    @admin.display(description='Vista previa firma')
    def signature_preview(self, obj):
        if obj.signature:
            return format_html(
                '<img src="{}" style="max-height:80px;background:#fff;border:1px solid #ddd;padding:4px;">',
                obj.signature.url,
            )
        return '—'
