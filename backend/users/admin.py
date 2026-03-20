from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Subscription, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        'id',
        'email',
        'username',
        'first_name',
        'last_name',
        'is_staff',
        'is_active',
    )
    search_fields = ('email', 'username')
    ordering = ('id',)
    fieldsets = BaseUserAdmin.fieldsets + (
        (
            'Дополнительно',
            {'fields': ('avatar',)},
        ),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        (
            'Дополнительно',
            {'fields': ('email', 'avatar')},
        ),
    )


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'user',
        'author',
        'created_at',
    )
    search_fields = (
        'user__email',
        'user__username',
        'author__email',
        'author__username',
    )
    autocomplete_fields = ('user', 'author')
