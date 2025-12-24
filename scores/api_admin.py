"""
Admin configuration for API tokens.
Allows Django admins to generate and manage API tokens for team admins.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token


class CustomTokenAdmin(admin.ModelAdmin):
    """
    Enhanced token admin with better display and filtering.
    """
    list_display = ('key', 'user', 'user_team', 'created')
    list_filter = ('created',)
    search_fields = ('user__username', 'user__email', 'key')
    ordering = ('-created',)
    readonly_fields = ('key', 'created')
    
    fieldsets = (
        (None, {
            'fields': ('user',)
        }),
        ('Token Information', {
            'fields': ('key', 'created'),
            'description': 'Token is automatically generated when saved.'
        }),
    )
    
    def user_team(self, obj):
        """Display the team associated with the user."""
        if hasattr(obj.user, 'team_admin'):
            return obj.user.team_admin.team.name
        return '-'
    user_team.short_description = 'Team'
    
    def has_change_permission(self, request, obj=None):
        """Tokens cannot be changed, only created or deleted."""
        return False
    
    def save_model(self, request, obj, form, change):
        """Generate new token on save."""
        if not change:  # Only on creation
            obj.save()


# Register the custom token admin
admin.site.register(Token, CustomTokenAdmin)


# Inline admin for managing tokens directly from user admin
class TokenInline(admin.StackedInline):
    """Display and manage user's API token from user admin page."""
    model = Token
    can_delete = True
    verbose_name = 'API Token'
    verbose_name_plural = 'API Token'
    readonly_fields = ('key', 'created')
    extra = 0
    max_num = 1
    
    fieldsets = (
        (None, {
            'fields': ('key', 'created'),
            'description': 'API token for REST API access. Token is auto-generated and cannot be changed. Delete to regenerate.'
        }),
    )


# Extend User admin to include token management
class UserAdminWithToken(BaseUserAdmin):
    """User admin with inline token management."""
    inlines = list(BaseUserAdmin.inlines) + [TokenInline]


# Re-register User admin with token support
admin.site.unregister(User)
admin.site.register(User, UserAdminWithToken)
