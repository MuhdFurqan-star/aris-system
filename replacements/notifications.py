# replacements/notifications.py
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.models import User
from .models import Notification, ClassReplacementRequest


def _create(recipient, notif_type, title, message, related_request=None):
    Notification.objects.create(
        recipient=recipient,
        notif_type=notif_type,
        title=title,
        message=message,
        related_request=related_request,
    )


def _send_email(to_email, subject, body):
    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[to_email],
            fail_silently=True,
        )
    except Exception:
        pass


# ── Public helpers called from views ──────────────────────────────────────────

def notify_request_submitted(replacement_request):
    """Notify the lecturer that their request was received, and all admins."""
    lecturer = replacement_request.lecturer
    subj = f"[CRS] Replacement Request Submitted — {replacement_request.subject.subject_code}"
    msg = (
        f"Hi {lecturer.first_name},\n\n"
        f"Your replacement class request for {replacement_request.subject.subject_name} "
        f"on {replacement_request.replacement_date} has been submitted and is pending approval.\n\n"
        f"Original date : {replacement_request.original_date} {replacement_request.original_time_slot}\n"
        f"Replacement   : {replacement_request.replacement_date} {replacement_request.replacement_time_slot}\n"
        f"Venue         : {replacement_request.venue.venue_name}\n\n"
        f"You will be notified once an admin reviews your request.\n\nARIS — Academic Replacement Intelligence System"
    )
    _create(lecturer, 'request_submitted', 'Request Submitted', msg, replacement_request)
    _send_email(lecturer.email, subj, msg)

    # Notify all admins
    admins = User.objects.filter(userprofile__user_type='admin')
    for admin in admins:
        admin_msg = (
            f"Hi {admin.first_name},\n\n"
            f"A new replacement request has been submitted by {lecturer.get_full_name()} "
            f"for {replacement_request.subject.subject_name}.\n\n"
            f"Please log in to review and approve or reject it.\n\nARIS — Academic Replacement Intelligence System"
        )
        _create(admin, 'request_submitted', f'New Request by {lecturer.get_full_name()}', admin_msg, replacement_request)
        _send_email(admin.email, f"[CRS] New Request — {replacement_request.subject.subject_code}", admin_msg)


def notify_request_approved(replacement_request):
    """Notify lecturer of approval + notify all students via in-app."""
    lecturer = replacement_request.lecturer
    subj = f"[CRS] Request Approved — {replacement_request.subject.subject_code}"
    msg = (
        f"Hi {lecturer.first_name},\n\n"
        f"Great news! Your replacement class for {replacement_request.subject.subject_name} "
        f"has been APPROVED.\n\n"
        f"Replacement : {replacement_request.replacement_date} {replacement_request.replacement_time_slot}\n"
        f"Venue       : {replacement_request.venue.venue_name} ({replacement_request.venue.location})\n\n"
        f"Students have been notified.\n\nARIS — Academic Replacement Intelligence System"
    )
    _create(lecturer, 'request_approved', 'Request Approved', msg, replacement_request)
    _send_email(lecturer.email, subj, msg)

    # Notify all students in-app
    students = User.objects.filter(userprofile__user_type='student')
    student_msg = (
        f"A new replacement class is now available!\n\n"
        f"Subject  : {replacement_request.subject.subject_name} ({replacement_request.subject.subject_code})\n"
        f"Lecturer : {lecturer.get_full_name()}\n"
        f"Date     : {replacement_request.replacement_date} {replacement_request.replacement_time_slot}\n"
        f"Venue    : {replacement_request.venue.venue_name}"
    )
    for student in students:
        _create(
            student, 'new_replacement',
            f'New Replacement: {replacement_request.subject.subject_code}',
            student_msg, replacement_request
        )


def notify_request_rejected(replacement_request):
    """Notify lecturer of rejection."""
    lecturer = replacement_request.lecturer
    subj = f"[CRS] Request Rejected — {replacement_request.subject.subject_code}"
    msg = (
        f"Hi {lecturer.first_name},\n\n"
        f"Unfortunately, your replacement class request for {replacement_request.subject.subject_name} "
        f"on {replacement_request.replacement_date} has been REJECTED.\n\n"
        f"Please contact the administration for more details or submit a new request.\n\nARIS — Academic Replacement Intelligence System"
    )
    _create(lecturer, 'request_rejected', 'Request Rejected', msg, replacement_request)
    _send_email(lecturer.email, subj, msg)


def notify_feedback_submitted(feedback):
    """Notify all admins when a lecturer submits a venue issue."""
    admins = User.objects.filter(userprofile__user_type='admin')
    severity_label = feedback.get_issue_status_display()
    msg = (
        f"A venue issue has been reported.\n\n"
        f"Venue    : {feedback.venue.venue_name}\n"
        f"Reporter : {feedback.lecturer.get_full_name()}\n"
        f"Severity : {severity_label}\n"
        f"Details  : {feedback.feedback_text[:200]}"
    )
    for admin in admins:
        _create(
            admin, 'feedback_submitted',
            f'[{severity_label}] Issue at {feedback.venue.venue_name}',
            msg
        )
        _send_email(
            admin.email,
            f"[CRS] Venue Issue Reported — {feedback.venue.venue_name}",
            msg
        )


def notify_issue_resolved(feedback):
    """Notify the lecturer when their reported venue issue is resolved."""
    msg = (
        f"Hi {feedback.lecturer.first_name},\n\n"
        f"The issue you reported at {feedback.venue.venue_name} has been resolved by the maintenance team.\n\n"
        f"Thank you for helping keep our venues in good condition!\n\nARIS — Academic Replacement Intelligence System"
    )
    _create(
        feedback.lecturer, 'issue_resolved',
        f'Issue Resolved — {feedback.venue.venue_name}', msg
    )
    _send_email(feedback.lecturer.email, f"[CRS] Issue Resolved — {feedback.venue.venue_name}", msg)
