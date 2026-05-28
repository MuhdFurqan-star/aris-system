# replacements/admin.py
from django.contrib import admin
from django.contrib.auth.models import User
from .models import UserProfile, Semester, Subject, Venue, ClassReplacementRequest, VenueFeedback


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'user_type', 'student_id', 'employee_id', 'get_email', 'get_full_name']
    list_filter = ['user_type']
    search_fields = ['user__username', 'user__email', 'student_id', 'employee_id']
    
    def get_email(self, obj):
        return obj.user.email
    get_email.short_description = 'Email'
    
    def get_full_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}"
    get_full_name.short_description = 'Full Name'


class UserAdmin(admin.ModelAdmin):
    list_display = ['username', 'email', 'first_name', 'last_name', 'is_active', 'date_joined']
    list_filter = ['is_active', 'is_staff', 'date_joined']
    search_fields = ['username', 'email', 'first_name', 'last_name']


admin.site.unregister(User)
admin.site.register(User, UserAdmin)


@admin.register(Semester)
class SemesterAdmin(admin.ModelAdmin):
    list_display = ['name', 'class_name', 'start_date', 'end_date', 'is_active']  
    list_filter = ['is_active', 'name']
    search_fields = ['name', 'class_name']


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):  
    list_display = ['subject_code', 'subject_name', 'semester', 'lecturer']  
    list_filter = ['semester']
    search_fields = ['subject_code', 'subject_name']


@admin.register(Venue)
class VenueAdmin(admin.ModelAdmin):
    list_display = ['venue_name', 'capacity', 'location', 'is_active']
    list_filter = ['is_active']
    search_fields = ['venue_name', 'location']


@admin.register(ClassReplacementRequest)
class ClassReplacementRequestAdmin(admin.ModelAdmin):
    list_display = ['subject', 'lecturer', 'replacement_date', 'venue', 'status', 'created_at']  
    list_filter = ['status', 'replacement_date', 'created_at']
    search_fields = ['subject__subject_code', 'lecturer__username'] 
    readonly_fields = ['created_at', 'updated_at']

@admin.register(VenueFeedback)
class VenueFeedbackAdmin(admin.ModelAdmin):
    list_display = ['venue', 'lecturer', 'display_issue_status', 'created_at']
    list_filter = ['issue_status', 'venue', 'created_at']
    search_fields = ['venue__venue_name', 'lecturer__username', 'lecturer__first_name', 'lecturer__last_name', 'feedback_text']
    readonly_fields = ['created_at']
    
    def display_issue_status(self, obj):
        status_icons = {
            'moderate': '⚠️ Moderate',
            'critical': '🚨 Critical',
            'solved': '✅ Solved'
        }
        return status_icons.get(obj.issue_status, obj.issue_status)
    
    display_issue_status.short_description = 'Issue Status'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('venue', 'lecturer')