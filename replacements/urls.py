# replacements/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Authentication
    path('', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # Student URLs
    path('student/dashboard/', views.student_dashboard, name='student_dashboard'),
    path('student/search/', views.student_search_replacements, name='student_search_replacements'),
    path('student/bookmark/<int:pk>/', views.student_toggle_bookmark, name='student_toggle_bookmark'),
    
    # Lecturer URLs
    path('lecturer/dashboard/', views.lecturer_dashboard, name='lecturer_dashboard'),
    path('lecturer/create-request/', views.lecturer_create_request, name='lecturer_create_request'),
    path('lecturer/view-requests/', views.lecturer_view_requests, name='lecturer_view_requests'),
    path('lecturer/past-replacements/', views.lecturer_past_replacements, name='lecturer_past_replacements'),
    path('lecturer/venue-feedback/', views.lecturer_venue_feedback, name='lecturer_venue_feedback'),
    path('lecturer/my-classes/', views.lecturer_my_classes, name='lecturer_my_classes'),
    path('lecturer/class-timetable/<int:sem_id>/', views.lecturer_class_timetable, name='lecturer_class_timetable'),
    
    # Admin URLs
    path('admin-portal/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-portal/requests/', views.admin_manage_requests, name='admin_manage_requests'),  
    path('admin-portal/approve/<int:request_id>/', views.admin_approve_request, name='admin_approve_request'),
    path('admin-portal/reject/<int:request_id>/', views.admin_reject_request, name='admin_reject_request'),
    path('admin-portal/venues/', views.admin_manage_venues, name='admin_manage_venues'),
    path('admin-portal/venues/add/', views.admin_add_venue, name='admin_add_venue'),
    path('admin-portal/venues/update/<int:venue_id>/', views.admin_update_venue, name='admin_update_venue'),
    path('admin-portal/venues/delete/<int:venue_id>/', views.admin_delete_venue, name='admin_delete_venue'),
    path('admin-portal/venues/toggle/<int:venue_id>/', views.admin_toggle_venue_status, name='admin_toggle_venue_status'),
    path('admin-portal/venues/<int:venue_id>/block/', views.admin_add_venue_block, name='admin_add_venue_block'),
    path('admin-portal/venues/block/<int:block_id>/delete/', views.admin_delete_venue_block, name='admin_delete_venue_block'),
    path('admin-portal/feedback/', views.admin_view_feedback, name='admin_view_feedback'),
    path('admin-portal/reports/replacement/', views.admin_generate_replacement_report, name='admin_generate_replacement_report'),
    path('admin-portal/reports/feedback/', views.admin_generate_feedback_report, name='admin_generate_feedback_report'),
    path('admin-portal/feedback/resolve/<int:pk>/', views.admin_resolve_feedback, name='admin_resolve_feedback'),
    path('admin-portal/feedback/unresolve/<int:pk>/', views.admin_unresolve_feedback, name='admin_unresolve_feedback'),
    path('admin-portal/reports/replacement/export/',
         views.export_replacement_report_csv, 
         name='export_replacement_report_csv'),
    
    path('admin-portal/reports/feedback/export/', 
         views.export_feedback_report_csv, 
         name='export_feedback_report_csv'),
         
    path('replacements/ai-suggest/', views.ai_suggest_slots, name='ai_suggest_slots'),
    path('replacements/check-conflict/', views.check_slot_conflict, name='check_slot_conflict'),
    path('replacements/venue-search/', views.venue_search_available, name='venue_search_available'),

    # Notifications
    path('notifications/', views.get_notifications, name='get_notifications'),
    path('notifications/read-all/', views.mark_notifications_read, name='mark_notifications_read'),
    path('notifications/read/<int:pk>/', views.mark_single_notification_read, name='mark_single_notification_read'),

    # QR Attendance — replacement classes (existing)
    path('lecturer/qr/<int:request_id>/', views.lecturer_generate_qr, name='lecturer_generate_qr'),
    path('lecturer/qr/toggle/<int:session_id>/', views.lecturer_toggle_qr_session, name='lecturer_toggle_qr_session'),
    # QR Attendance — regular timetable classes (new)
    path('lecturer/schedule-qr/<int:schedule_id>/', views.lecturer_generate_schedule_qr, name='lecturer_generate_schedule_qr'),
    # Attendance scan (handles both types)
    path('attendance/scan/<str:token>/', views.student_scan_qr, name='student_scan_qr'),
    # Student in-app scanner
    path('student/scan/', views.student_scan_qr_page, name='student_scan_qr_page'),
    # Attendance reports
    path('lecturer/attendance/report/', views.lecturer_attendance_report, name='lecturer_attendance_report'),
    path('lecturer/attendance/session/<int:session_id>/', views.lecturer_attendance_session_detail, name='lecturer_attendance_session_detail'),

    # Chart data (JSON)
    path('admin-portal/chart-data/', views.admin_chart_data, name='admin_chart_data'),
    path('lecturer/chart-data/', views.lecturer_chart_data, name='lecturer_chart_data'),

    # PDF exports
    path('admin-portal/reports/replacement/pdf/', views.export_replacement_report_pdf, name='export_replacement_report_pdf'),
    path('admin-portal/reports/feedback/pdf/', views.export_feedback_report_pdf, name='export_feedback_report_pdf'),

    # PWA offline page
    path('offline/', views.offline_view, name='offline'),

    # iCal / Calendar export
    path('student/export/ical/', views.export_ical_bookmarks, name='export_ical_bookmarks'),
    path('export/ical/<int:pk>/', views.export_ical_single, name='export_ical_single'),

    # Venue heatmap
    path('admin-portal/heatmap/', views.admin_venue_heatmap, name='admin_venue_heatmap'),

    # Timetable
    path('timetable/', views.timetable_view, name='timetable_view'),

    # AI Chatbot
    path('chatbot/', views.chatbot_view, name='chatbot_view'),
    path('chatbot/api/', views.chatbot_api, name='chatbot_api'),

    # Admin — User Management
    path('admin-portal/users/', views.admin_manage_users, name='admin_manage_users'),
    path('admin-portal/users/add/', views.admin_add_user, name='admin_add_user'),
    path('admin-portal/users/<int:user_id>/edit/', views.admin_edit_user, name='admin_edit_user'),
    path('admin-portal/users/<int:user_id>/delete/', views.admin_delete_user, name='admin_delete_user'),
    path('admin-portal/users/<int:user_id>/reset-password/', views.admin_reset_password, name='admin_reset_password'),

    # Admin — Semester / Class Management
    path('admin-portal/semesters/', views.admin_manage_semesters, name='admin_manage_semesters'),
    path('admin-portal/semesters/add/', views.admin_add_semester, name='admin_add_semester'),
    path('admin-portal/semesters/<int:sem_id>/edit/', views.admin_edit_semester, name='admin_edit_semester'),
    path('admin-portal/semesters/<int:sem_id>/delete/', views.admin_delete_semester, name='admin_delete_semester'),
    path('admin-portal/semesters/<int:sem_id>/assign/', views.admin_semester_assign, name='admin_semester_assign'),

    # Admin — Subject Management
    path('admin-portal/subjects/', views.admin_manage_subjects, name='admin_manage_subjects'),
    path('admin-portal/subjects/add/', views.admin_add_subject, name='admin_add_subject'),
    path('admin-portal/subjects/<int:sub_id>/', views.admin_subject_detail, name='admin_subject_detail'),
    path('admin-portal/subjects/<int:sub_id>/edit/', views.admin_edit_subject, name='admin_edit_subject'),
    path('admin-portal/subjects/<int:sub_id>/delete/', views.admin_delete_subject, name='admin_delete_subject'),

    # Admin — Lecturer Detail
    path('admin-portal/lecturers/<int:user_id>/', views.admin_lecturer_detail, name='admin_lecturer_detail'),

    # Admin — Enrollment Management
    path('admin-portal/enrollments/', views.admin_manage_enrollments, name='admin_manage_enrollments'),
    path('admin-portal/enrollments/assign/', views.admin_assign_students, name='admin_assign_students'),
    path('admin-portal/enrollments/remove/<int:enr_id>/', views.admin_remove_enrollment, name='admin_remove_enrollment'),
]