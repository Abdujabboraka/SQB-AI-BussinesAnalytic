from django.contrib import admin
from .models import UserProfile, BusinessAnalysisRequest, SystemConfiguration


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'phone', 'created_at']
    list_filter = ['role']
    search_fields = ['user__username', 'user__email']


@admin.register(BusinessAnalysisRequest)
class BusinessAnalysisRequestAdmin(admin.ModelAdmin):
    list_display = [
        'business_type', 'district', 'client', 'status',
        'final_recommendation', 'final_score', 'credit_tier', 'created_at'
    ]
    list_filter = ['status', 'final_recommendation', 'district', 'mcc_code']
    search_fields = ['business_type', 'client__username']
    readonly_fields = ['created_at', 'updated_at', 'celery_task_id']
    ordering = ['-created_at']

@admin.register(SystemConfiguration)
class SystemConfigurationAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'active_ai_provider', 'updated_at']
    
    def has_add_permission(self, request):
        # Prevent adding more than one instance
        if self.model.objects.count() >= 1:
            return False
        return super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        # Prevent deleting the configuration
        return False
