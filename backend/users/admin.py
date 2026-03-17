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
    )
    search_fields = ('email', 'username')
    list_filter = ('is_staff', 'is_superuser', 'is_active')
    ordering = ('id',)

    fieldsets = BaseUserAdmin.fieldsets + (
        ('Дополнительно', {'fields': ('avatar',)}),
    )


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'author', 'created_at')
    search_fields = (
        'user__email',
        'user__username',
        'author__email',
        'author__username',
    )
    list_filter = ('created_at',)
