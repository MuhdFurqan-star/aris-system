# replacements/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Avg, Count, Q
from django.db import models
from .forms import UserRegistrationForm
from .models import *
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.models import User
from django.views.decorators.http import require_GET
from datetime import datetime, timedelta
from django.utils import timezone as tz
import csv
import uuid
import qrcode
import io
import base64
from .notifications import (
    notify_request_submitted, notify_request_approved,
    notify_request_rejected, notify_feedback_submitted,
    notify_issue_resolved,
)
from .models import Notification, AttendanceSession, AttendanceRecord

# ==================== AUTHENTICATION VIEWS ====================

def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f'Account created successfully! You can now log in.')
            return redirect('login')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = UserRegistrationForm()
    
    return render(request, 'authentication/register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        password = request.POST.get('password')
        selected_user_type = request.POST.get('user_type')
        
        if not selected_user_type:
            messages.error(request, 'Please select your user type.')
            return render(request, 'authentication/login.html')
        
        if not user_id or not password:
            messages.error(request, 'Please enter both ID and password.')
            return render(request, 'authentication/login.html')
        
        try:
            if selected_user_type == 'student':
                user_profile = UserProfile.objects.get(student_id=user_id, user_type='student')
            elif selected_user_type == 'lecturer':
                user_profile = UserProfile.objects.get(employee_id=user_id, user_type='lecturer')
            elif selected_user_type == 'admin':
                user_profile = UserProfile.objects.get(employee_id=user_id, user_type='admin')
            else:
                messages.error(request, 'Invalid user type selected.')
                return render(request, 'authentication/login.html')
            
            username = user_profile.user.username
            user = authenticate(request, username=username, password=password)
            
            if user is not None:
                login(request, user)
                messages.success(request, f'Welcome back, {user.first_name}!')
                return redirect('dashboard')
            else:
                messages.error(request, 'Invalid ID or password.')
        
        except UserProfile.DoesNotExist:
            messages.error(request, f'No {selected_user_type} account found with this ID.')
        except Exception as e:
            messages.error(request, 'An error occurred. Please try again.')
    
    return render(request, 'authentication/login.html')


def logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('login')


@login_required
def dashboard(request):
    user_type = request.user.userprofile.user_type
    
    if user_type == 'student':
        return redirect('student_dashboard')
    elif user_type == 'lecturer':
        return redirect('lecturer_dashboard')
    elif user_type == 'admin':
        return redirect('admin_dashboard')
    else:
        return render(request, 'home.html')


# ==================== STUDENT VIEWS ====================

@login_required
def student_dashboard(request):
    """Student dashboard showing bookmarked replacements"""
    if not hasattr(request.user, 'userprofile') or request.user.userprofile.user_type != 'student':
        messages.error(request, 'Access denied. Student privileges required.')
        return redirect('dashboard')
    
    from django.utils import timezone
    
    bookmarked_replacements = ClassReplacementRequest.objects.filter(
        bookmarked_by__student=request.user,
        status='approved'
    ).select_related(
        'subject',
        'subject__semester',
        'lecturer',
        'venue'
    ).prefetch_related('bookmarked_by').order_by('replacement_date', 'replacement_time_slot')
    
    today = timezone.now().date()
    upcoming_bookmarks = bookmarked_replacements.filter(replacement_date__gte=today)
    past_bookmarks = bookmarked_replacements.filter(replacement_date__lt=today)
    
    bookmarked_ids = list(request.user.bookmarks.values_list('replacement_id', flat=True))
    
    context = {
        'upcoming_bookmarks': upcoming_bookmarks,
        'past_bookmarks': past_bookmarks,
        'bookmarked_ids': bookmarked_ids,
        'today': today,
    }
    
    return render(request, 'student/dashboard_student.html', context)


@login_required
def student_search_replacements(request):
    """Search and filter all approved class replacements"""
    if not hasattr(request.user, 'userprofile') or request.user.userprofile.user_type != 'student':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    from django.utils import timezone
    
    search_query = request.GET.get('search', '')
    semester_id = request.GET.get('semester', '')
    date_filter = request.GET.get('date_filter', 'upcoming')
    
    replacements = ClassReplacementRequest.objects.filter(
        status='approved'
    ).select_related(
        'subject',
        'subject__semester',
        'lecturer',
        'venue'
    ).prefetch_related('bookmarked_by')
    
    today = timezone.now().date()
    if date_filter == 'upcoming':
        replacements = replacements.filter(replacement_date__gte=today)
    elif date_filter == 'past':
        replacements = replacements.filter(replacement_date__lt=today)
    
    if semester_id:
        replacements = replacements.filter(subject__semester_id=semester_id)
    
    if search_query:
        replacements = replacements.filter(
            Q(subject__subject_code__icontains=search_query) |
            Q(subject__subject_name__icontains=search_query) |
            Q(lecturer__first_name__icontains=search_query) |
            Q(lecturer__last_name__icontains=search_query) |
            Q(venue__venue_name__icontains=search_query)
        )
    
    replacements = replacements.order_by('replacement_date', 'replacement_time_slot')
    
    semesters = Semester.objects.filter(is_active=True).order_by('name', 'class_name')
    bookmarked_ids = list(request.user.bookmarks.values_list('replacement_id', flat=True))
    
    context = {
        'replacements': replacements,
        'semesters': semesters,
        'search_query': search_query,
        'selected_semester': semester_id,
        'date_filter': date_filter,
        'bookmarked_ids': bookmarked_ids,
    }
    
    return render(request, 'student/search_replacements.html', context)


@login_required
def student_toggle_bookmark(request, pk):
    """Toggle bookmark for a replacement (AJAX)"""
    if not hasattr(request.user, 'userprofile') or request.user.userprofile.user_type != 'student':
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method'}, status=405)
    
    replacement = get_object_or_404(ClassReplacementRequest, pk=pk, status='approved')
    
    bookmark = ReplacementBookmark.objects.filter(
        student=request.user,
        replacement=replacement
    ).first()
    
    if bookmark:
        bookmark.delete()
        return JsonResponse({'status': 'removed', 'message': 'Bookmark removed'})
    else:
        ReplacementBookmark.objects.create(
            student=request.user,
            replacement=replacement
        )
        return JsonResponse({'status': 'added', 'message': 'Bookmark added'})


# ==================== LECTURER VIEWS ====================

@login_required
def lecturer_dashboard(request):
    """Lecturer dashboard with statistics and recent activity"""
    if not hasattr(request.user, 'userprofile') or request.user.userprofile.user_type != 'lecturer':
        messages.error(request, 'Access denied. Lecturer privileges required.')
        return redirect('dashboard')
    
    lecturer_requests = ClassReplacementRequest.objects.filter(lecturer=request.user)
    
    total_requests    = lecturer_requests.count()
    pending_requests  = lecturer_requests.filter(status='pending').count()
    approved_requests = lecturer_requests.filter(status='approved').count()
    rejected_requests = lecturer_requests.filter(status='rejected').count()
    
    recent_requests = lecturer_requests.select_related(
        'subject', 'subject__semester', 'venue'
    ).order_by('-created_at')[:5]
    
    context = {
        'total_requests':    total_requests,
        'pending_requests':  pending_requests,
        'approved_requests': approved_requests,
        'rejected_requests': rejected_requests,
        'recent_requests':   recent_requests,
    }
    
    return render(request, 'lecturer/dashboard_lecturer.html', context)


@login_required
def lecturer_create_request(request):
    """Create new class replacement request"""
    if not hasattr(request.user, 'userprofile') or request.user.userprofile.user_type != 'lecturer':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        subject_id        = request.POST.get('subject')
        original_date     = request.POST.get('original_date')
        original_time     = request.POST.get('original_time_slot')
        replacement_date  = request.POST.get('replacement_date')
        replacement_time  = request.POST.get('replacement_time_slot')
        venue_id          = request.POST.get('venue')
        reason            = request.POST.get('reason')
        
        if not all([subject_id, original_date, original_time, replacement_date, replacement_time, venue_id, reason]):
            messages.error(request, 'All fields are required.')
            return redirect('lecturer_create_request')
        
        try:
            replacement_date_obj = datetime.strptime(replacement_date, '%Y-%m-%d').date()
            
            if replacement_date_obj < timezone.now().date():
                messages.error(request, 'Replacement date cannot be in the past.')
                return redirect('lecturer_create_request')
            
            try:
                venue = Venue.objects.get(id=venue_id, is_active=True)
            except Venue.DoesNotExist:
                messages.error(request, 'Selected venue is not available.')
                return redirect('lecturer_create_request')

            # Check admin block for this date
            if VenueBlock.objects.filter(venue_id=venue_id, blocked_date=replacement_date_obj).exists():
                messages.error(request, f'{venue.venue_name} has been blocked by admin on that date.')
                return redirect('lecturer_create_request')

            venue_conflict = ClassReplacementRequest.objects.filter(
                venue_id=venue_id,
                replacement_date=replacement_date,
                replacement_time_slot=replacement_time,
                status__in=['approved', 'pending']
            ).exists()

            if venue_conflict:
                messages.error(request, 'This venue already has a pending or approved booking for the selected date and time.')
                return redirect('lecturer_create_request')
            
            new_request = ClassReplacementRequest.objects.create(
                lecturer=request.user,
                subject_id=subject_id,
                original_date=original_date,
                original_time_slot=original_time,
                replacement_date=replacement_date,
                replacement_time_slot=replacement_time,
                venue_id=venue_id,
                reason=reason,
                status='pending'
            )
            notify_request_submitted(new_request)

            messages.success(request, 'Replacement request submitted successfully!')
            return redirect('lecturer_view_requests')
            
        except ValueError:
            messages.error(request, 'Invalid date format.')
            return redirect('lecturer_create_request')
        except Exception as e:
            messages.error(request, f'Error creating request: {str(e)}')
            return redirect('lecturer_create_request')
    
    my_subjects = Subject.objects.filter(lecturer=request.user).select_related('semester')

    if not my_subjects.exists():
        messages.warning(request, 'You have no subjects assigned. Please contact the administrator.')

    return render(request, 'lecturer/create_request.html', {
        'my_subjects':        my_subjects,
        'venue_type_choices': Venue.VENUE_TYPE_CHOICES,
    })


@login_required
def lecturer_view_requests(request):
    """View all replacement requests by status"""
    if not hasattr(request.user, 'userprofile') or request.user.userprofile.user_type != 'lecturer':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    pending = ClassReplacementRequest.objects.filter(
        lecturer=request.user, status='pending'
    ).select_related('subject', 'subject__semester', 'venue').order_by('-created_at')
    
    approved = ClassReplacementRequest.objects.filter(
        lecturer=request.user, status='approved'
    ).select_related('subject', 'subject__semester', 'venue').order_by('-replacement_date', '-replacement_time_slot')
    
    rejected = ClassReplacementRequest.objects.filter(
        lecturer=request.user, status='rejected'
    ).select_related('subject', 'subject__semester', 'venue').order_by('-created_at')
    
    context = {
        'pending':  pending,
        'approved': approved,
        'rejected': rejected,
    }
    
    return render(request, 'lecturer/view_requests.html', context)


@login_required
def lecturer_past_replacements(request):
    """View past approved replacements with filtering"""
    if not hasattr(request.user, 'userprofile') or request.user.userprofile.user_type != 'lecturer':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    today = timezone.now().date()
    
    past_replacements = ClassReplacementRequest.objects.filter(
        lecturer=request.user,
        status='approved',
        replacement_date__lt=today
    ).select_related('subject', 'subject__semester', 'venue', 'approved_by')
    
    search_query = request.GET.get('search', '')
    from_date    = request.GET.get('from_date', '')
    to_date      = request.GET.get('to_date', '')
    
    if search_query:
        past_replacements = past_replacements.filter(
            Q(subject__subject_code__icontains=search_query) |
            Q(subject__subject_name__icontains=search_query) |
            Q(venue__venue_name__icontains=search_query) |
            Q(venue__location__icontains=search_query)
        )
    
    if from_date:
        try:
            from_date_obj = datetime.strptime(from_date, '%Y-%m-%d').date()
            past_replacements = past_replacements.filter(replacement_date__gte=from_date_obj)
        except ValueError:
            pass
    
    if to_date:
        try:
            to_date_obj = datetime.strptime(to_date, '%Y-%m-%d').date()
            past_replacements = past_replacements.filter(replacement_date__lte=to_date_obj)
        except ValueError:
            pass
    
    past_replacements = past_replacements.order_by('-replacement_date', '-replacement_time_slot')
    
    unique_subjects = past_replacements.values('subject__subject_code').distinct().count()
    unique_venues   = past_replacements.values('venue__venue_name').distinct().count()
    
    context = {
        'past_replacements': past_replacements,
        'unique_subjects':   unique_subjects,
        'unique_venues':     unique_venues,
    }
    
    return render(request, 'lecturer/past_replacements.html', context)


@login_required
def lecturer_venue_feedback(request):
    """Submit feedback for venues - Report issues and damage"""
    if not hasattr(request.user, 'userprofile') or request.user.userprofile.user_type != 'lecturer':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        venue_id      = request.POST.get('venue')
        request_id    = request.POST.get('replacement_request')
        feedback_text = request.POST.get('feedback_text')
        severity      = request.POST.get('severity')
        
        issues = []
        issue_types = {
            'issue_aircon':       'Air Conditioning',
            'issue_projector':    'Projector',
            'issue_audio':        'Audio System',
            'issue_lighting':     'Lighting',
            'issue_furniture':    'Furniture/Tables',
            'issue_cleanliness':  'Cleanliness',
            'issue_internet':     'Internet/WiFi',
            'issue_electrical':   'Electrical/Power',
            'issue_door':         'Door/Windows',
            'issue_whiteboard':   'Whiteboard',
            'issue_safety':       'Safety Hazard',
            'issue_other':        'Other'
        }
        
        for key, label in issue_types.items():
            if request.POST.get(key):
                issues.append(label)
        
        if issues:
            issues_text   = "\n\n[Issues Reported: " + ", ".join(issues) + "]"
            feedback_text = feedback_text + issues_text
        
        if not all([venue_id, feedback_text, severity]):
            messages.error(request, 'Venue, description, and severity level are required.')
            return redirect('lecturer_venue_feedback')
        
        try:
            try:
                venue = Venue.objects.get(id=venue_id)
            except Venue.DoesNotExist:
                messages.error(request, 'Selected venue does not exist.')
                return redirect('lecturer_venue_feedback')
            
            new_feedback = VenueFeedback.objects.create(
                lecturer=request.user,
                venue_id=venue_id,
                replacement_request_id=request_id if request_id else None,
                feedback_text=feedback_text,
                issue_status=severity
            )
            notify_feedback_submitted(new_feedback)

            messages.success(request, 'Issue report submitted successfully. The maintenance team will be notified.')
            return redirect('lecturer_venue_feedback')
            
        except Exception as e:
            messages.error(request, f'Error submitting report: {str(e)}')
            return redirect('lecturer_venue_feedback')
    
    venues = Venue.objects.filter(is_active=True).order_by('venue_name')
    
    my_past_requests = ClassReplacementRequest.objects.filter(
        lecturer=request.user, status='approved'
    ).select_related('subject', 'subject__semester', 'venue').order_by('-replacement_date')[:20]
    
    my_feedback = VenueFeedback.objects.filter(
        lecturer=request.user
    ).select_related('venue', 'replacement_request', 'replacement_request__subject').order_by('-created_at')
    
    context = {
        'venues':           venues,
        'my_past_requests': my_past_requests,
        'my_feedback':      my_feedback,
    }
    
    return render(request, 'lecturer/venue_feedback.html', context)


# ==================== AI SMART SLOT SUGGESTION VIEWS ====================

@login_required
@require_GET
def ai_suggest_slots(request):
    """
    AJAX endpoint — returns AI-powered replacement slot suggestions.
    URL: /replacements/ai-suggest/?original_date=2025-11-20

    Logic:
    - Analyzes lecturer's past approved replacement patterns
    - Finds preferred days of week and preferred venues
    - Returns top 3 available slots with confidence rating
    """
    if not hasattr(request.user, 'userprofile') or request.user.userprofile.user_type != 'lecturer':
        return JsonResponse({'error': 'Access denied. Lecturer only.'}, status=403)

    original_date_str = request.GET.get('original_date')
    if not original_date_str:
        return JsonResponse({'error': 'original_date parameter is required.'}, status=400)

    try:
        original_date = datetime.strptime(original_date_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'error': 'Invalid date format. Use YYYY-MM-DD.'}, status=400)

    try:
        suggestions = _generate_ai_suggestions(
            lecturer_id=request.user.id,
            original_date=original_date,
            num_suggestions=3
        )
        return JsonResponse({'suggestions': suggestions})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def _parse_time_range(slot_str):
    """
    Parse a time-slot string into (start_time, end_time) datetime.time objects.
    Supports:
      - '08:00-10:00'  (24-hour, no space)
      - '8:00 AM - 10:00 AM'  (12-hour with AM/PM)
    Returns (None, None) if parsing fails.
    """
    import re as _re
    from datetime import time as _time

    s = slot_str.strip() if slot_str else ''

    # 24-hour: HH:MM-HH:MM (with optional space around dash)
    m = _re.match(r'^(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})$', s)
    if m:
        try:
            return _time(int(m.group(1)), int(m.group(2))), _time(int(m.group(3)), int(m.group(4)))
        except ValueError:
            return None, None

    # 12-hour: 8:00 AM - 10:00 AM
    m = _re.match(r'^(\d{1,2}):(\d{2})\s*(AM|PM)\s*-\s*(\d{1,2}):(\d{2})\s*(AM|PM)$', s, _re.I)
    if m:
        try:
            h1, mi1, ap1 = int(m.group(1)), int(m.group(2)), m.group(3).upper()
            h2, mi2, ap2 = int(m.group(4)), int(m.group(5)), m.group(6).upper()
            if ap1 == 'PM' and h1 != 12: h1 += 12
            if ap1 == 'AM' and h1 == 12: h1 = 0
            if ap2 == 'PM' and h2 != 12: h2 += 12
            if ap2 == 'AM' and h2 == 12: h2 = 0
            return _time(h1, mi1), _time(h2, mi2)
        except ValueError:
            return None, None

    return None, None


@login_required
@require_GET
def check_slot_conflict(request):
    """
    AJAX endpoint — real-time conflict checker when lecturer picks venue/date/time.
    URL: /replacements/check-conflict/?venue_id=1&date=2025-11-20&time_slot=10:00-11:00
    """
    venue_id  = request.GET.get('venue_id')
    date_str  = request.GET.get('date')
    time_slot = request.GET.get('time_slot')

    if not all([venue_id, date_str, time_slot]):
        return JsonResponse({'error': 'Missing parameters: venue_id, date, time_slot required.'}, status=400)

    conflict = ClassReplacementRequest.objects.filter(
        venue_id=venue_id,
        replacement_date=date_str,
        replacement_time_slot=time_slot,
        status__in=['approved', 'pending']
    ).first()

    if conflict:
        lecturer_name = conflict.lecturer.get_full_name() or conflict.lecturer.username
        return JsonResponse({
            'has_conflict': True,
            'conflicting_subject': conflict.subject.subject_name,
            'conflicting_lecturer': lecturer_name,
            'message': f"Already booked by {conflict.subject.subject_name} ({lecturer_name})"
        })

    return JsonResponse({'has_conflict': False})


@login_required
@require_GET
def venue_search_available(request):
    """
    AJAX endpoint — returns venues free for a given date + time slot.
    GET params: date=YYYY-MM-DD, time_slot=HH:MM-HH:MM,
                venue_type= (optional), min_capacity= (optional)
    """
    from datetime import date as _date

    date_str  = request.GET.get('date', '').strip()
    time_slot = request.GET.get('time_slot', '').strip()
    vtype     = request.GET.get('venue_type', '').strip()
    min_cap   = request.GET.get('min_capacity', '').strip()

    if not date_str or not time_slot:
        return JsonResponse({'error': 'date and time_slot are required'}, status=400)

    try:
        req_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=400)

    req_start, req_end = _parse_time_range(time_slot)
    if req_start is None:
        return JsonResponse({'error': 'Invalid time_slot format. Use HH:MM-HH:MM'}, status=400)

    # --- Base queryset ---
    venues_qs = Venue.objects.filter(is_active=True)
    if vtype:
        venues_qs = venues_qs.filter(venue_type=vtype)
    if min_cap:
        try:
            venues_qs = venues_qs.filter(capacity__gte=int(min_cap))
        except ValueError:
            pass

    # --- 1. Venues blocked by admin on this date ---
    blocked_ids = set(
        VenueBlock.objects.filter(blocked_date=req_date).values_list('venue_id', flat=True)
    )

    # --- 2. Venues with overlapping replacement requests (pending/approved) ---
    conflicted_by_req = set()
    req_conflicts = ClassReplacementRequest.objects.filter(
        replacement_date=req_date,
        status__in=['pending', 'approved']
    ).values_list('venue_id', 'replacement_time_slot')
    for vid, slot in req_conflicts:
        s, e = _parse_time_range(slot)
        if s and e and req_start < e and s < req_end:
            conflicted_by_req.add(vid)

    # --- 3. Venues with regular classes scheduled on this weekday/time ---
    day_of_week = req_date.weekday()   # 0 = Monday
    conflicted_by_sched = set()
    sched_rows = ClassSchedule.objects.filter(
        venue__isnull=False,
        day_of_week=day_of_week,
    ).values_list('venue_id', 'start_time', 'end_time')
    for vid, s_start, s_end in sched_rows:
        if req_start < s_end and s_start < req_end:
            conflicted_by_sched.add(vid)

    excluded = blocked_ids | conflicted_by_req | conflicted_by_sched
    available = venues_qs.exclude(id__in=excluded)

    # Type-to-icon mapping
    type_icon = {
        'classroom': 'fa-chalkboard',
        'lab':       'fa-desktop',
        'workshop':  'fa-tools',
        'studio':    'fa-palette',
    }

    result = []
    for v in available.order_by('venue_name'):
        result.append({
            'id':           v.id,
            'name':         v.venue_name,
            'capacity':     v.capacity,
            'location':     v.location,
            'venue_type':   v.venue_type,
            'type_display': v.get_venue_type_display(),
            'icon':         type_icon.get(v.venue_type, 'fa-building'),
            'facilities':   v.facilities,
        })

    return JsonResponse({'available': result, 'count': len(result)})


# ---- Internal AI helper functions (not views, no URL needed) ----

def _get_available_time_slots():
    """Common replacement class time slots — 1-hour and 2-hour blocks."""
    return [
        "08:00-10:00", "09:00-11:00", "10:00-12:00",
        "11:00-13:00", "13:00-15:00", "14:00-16:00",
        "15:00-17:00", "16:00-18:00",
        "08:00-09:00", "09:00-10:00", "10:00-11:00",
        "11:00-12:00", "13:00-14:00", "14:00-15:00",
    ]


def _get_lecturer_preferred_days(lecturer_id, top_n=3):
    """Returns list of preferred weekday integers (0=Mon, 4=Fri) from history."""
    from collections import Counter

    past_dates = ClassReplacementRequest.objects.filter(
        lecturer_id=lecturer_id,
        status='approved'
    ).values_list('replacement_date', flat=True)

    if not past_dates.exists():
        return [0, 2, 4]  # Default Mon/Wed/Fri if no history

    day_counts = Counter([d.weekday() for d in past_dates])
    return [day for day, _ in day_counts.most_common(top_n)]


def _get_best_venues(lecturer_id, top_n=3):
    """Ranks venues by lecturer familiarity minus critical issue penalty."""
    used = ClassReplacementRequest.objects.filter(
        lecturer_id=lecturer_id,
        status='approved'
    ).values('venue_id').annotate(
        usage_count=Count('venue_id')
    ).order_by('-usage_count')

    # Map venue_id → rank index (0 = most used), O(1) lookup
    usage_rank = {v['venue_id']: i for i, v in enumerate(used)}

    problematic_ids = set(VenueFeedback.objects.filter(
        issue_status='critical'
    ).values_list('venue_id', flat=True))

    all_venues = list(Venue.objects.filter(is_active=True))

    scored = []
    for venue in all_venues:
        score = 0
        if venue.id in usage_rank:
            score += max(10 - usage_rank[venue.id], 1)
        if venue.id in problematic_ids:
            score -= 5
        scored.append((venue, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    return [v for v, _ in scored[:top_n]]


def _is_venue_available(venue_id, date, slot):
    """
    Returns True if the venue is free on the given date + time slot.
    Checks: replacement request bookings, VenueBlocks.
    """
    # 1. Admin block for this date
    if VenueBlock.objects.filter(venue_id=venue_id, blocked_date=date).exists():
        return False

    req_start, req_end = _parse_time_range(slot)
    if req_start is None:
        return False

    # 2. Overlapping replacement requests
    existing = ClassReplacementRequest.objects.filter(
        venue_id=venue_id,
        replacement_date=date,
        status__in=['approved', 'pending']
    ).values_list('replacement_time_slot', flat=True)

    for existing_slot in existing:
        s, e = _parse_time_range(existing_slot)
        if s and e and req_start < e and s < req_end:
            return False

    return True


def _generate_ai_suggestions(lecturer_id, original_date, num_suggestions=3):
    """
    Core AI logic — returns list of suggestion dicts ready for JSON response.
    Checks: preferred days from history, best venues from history,
            VenueBlocks, overlapping replacement bookings.
    """
    day_names      = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    preferred_days = _get_lecturer_preferred_days(lecturer_id)
    best_venues    = _get_best_venues(lecturer_id)
    all_slots      = _get_available_time_slots()

    has_history = ClassReplacementRequest.objects.filter(
        lecturer_id=lecturer_id,
        status='approved'
    ).exists()

    suggestions  = []
    check_date   = original_date + timedelta(days=1)
    days_checked = 0

    while len(suggestions) < num_suggestions and days_checked < 30:
        if check_date.weekday() < 5:  # Mon–Fri only
            is_preferred = check_date.weekday() in preferred_days

            for venue in best_venues:
                if len(suggestions) >= num_suggestions:
                    break

                for slot in all_slots:
                    if _is_venue_available(venue.id, check_date, slot):
                        if is_preferred and has_history:
                            confidence = 'High'
                            reason     = f"Matches your preferred day ({day_names[check_date.weekday()]}) and venue history"
                        elif has_history:
                            confidence = 'Medium'
                            reason     = "Preferred venue from your history, different day than usual"
                        else:
                            confidence = 'Low'
                            reason     = "No history yet — suggestion based on venue availability"

                        suggestions.append({
                            'date':           check_date.strftime('%Y-%m-%d'),
                            'day_name':       day_names[check_date.weekday()],
                            'time_slot':      slot,
                            'venue_id':       venue.id,
                            'venue_name':     venue.venue_name,
                            'venue_location': venue.location,
                            'capacity':       venue.capacity,
                            'confidence':     confidence,
                            'reason':         reason,
                        })
                        break  # One slot per venue per day

                if len(suggestions) >= num_suggestions:
                    break

        check_date   += timedelta(days=1)
        days_checked += 1

    return suggestions


# ==================== ADMIN VIEWS ====================

@login_required
def admin_dashboard(request):
    if request.user.userprofile.user_type != 'admin':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    pending_requests = ClassReplacementRequest.objects.filter(
        status='pending'
    ).select_related('lecturer', 'subject', 'subject__semester', 'venue')
    total_pending = pending_requests.count()
    
    today = timezone.now().date()
    total_approved_today = ClassReplacementRequest.objects.filter(
        status='approved',
        approved_by__isnull=False,
        updated_at__date=today
    ).count()
    
    total_venues   = Venue.objects.filter(is_active=True).count()
    total_feedback = VenueFeedback.objects.count()
    
    context = {
        'pending_requests':    pending_requests,
        'total_pending':       total_pending,
        'total_approved_today': total_approved_today,
        'total_venues':        total_venues,
        'total_feedback':      total_feedback,
    }
    
    return render(request, 'admin/dashboard_admin.html', context)


@login_required
def admin_approve_request(request, request_id):
    if request.user.userprofile.user_type != 'admin':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    replacement_request = get_object_or_404(ClassReplacementRequest, id=request_id)

    # Check that no other approved request already occupies the same venue/date/time
    conflict = ClassReplacementRequest.objects.filter(
        venue=replacement_request.venue,
        replacement_date=replacement_request.replacement_date,
        replacement_time_slot=replacement_request.replacement_time_slot,
        status='approved',
    ).exclude(pk=replacement_request.pk).exists()

    if conflict:
        messages.error(request, 'Cannot approve: another request already occupies that venue, date, and time slot.')
        return redirect('admin_manage_requests')

    replacement_request.status      = 'approved'
    replacement_request.approved_by = request.user
    replacement_request.save()
    notify_request_approved(replacement_request)

    messages.success(request, f'Request for {replacement_request.subject} has been approved.')
    return redirect('admin_manage_requests')


@login_required
def admin_reject_request(request, request_id):
    if request.user.userprofile.user_type != 'admin':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    replacement_request = get_object_or_404(ClassReplacementRequest, id=request_id)
    replacement_request.status = 'rejected'
    replacement_request.save()
    notify_request_rejected(replacement_request)

    messages.warning(request, f'Request for {replacement_request.subject} has been rejected.')
    return redirect('admin_manage_requests')


# ==================== ADMIN VENUE MANAGEMENT ====================


@login_required
def admin_manage_venues(request):
    if request.user.userprofile.user_type != 'admin':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    venues = Venue.objects.all().prefetch_related('blocks').order_by('-is_active', 'venue_name')
    today  = tz.localdate()
    return render(request, 'admin/manage_venues.html', {
        'venues':             venues,
        'today':              today,
        'venue_type_choices': Venue.VENUE_TYPE_CHOICES,
    })


@login_required
def admin_add_venue(request):
    if request.user.userprofile.user_type != 'admin':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        venue_name = request.POST.get('venue_name', '').strip()
        venue_type = request.POST.get('venue_type', 'classroom').strip()
        capacity   = request.POST.get('capacity')
        location   = request.POST.get('location', '').strip()
        facilities = request.POST.get('facilities', '')
        picture    = request.FILES.get('picture')

        if not all([venue_name, capacity, location]):
            messages.error(request, 'Venue name, capacity, and location are required.')
            return render(request, 'admin/add_venue.html',
                          {'venue_type_choices': Venue.VENUE_TYPE_CHOICES})

        try:
            capacity_int = int(capacity)
            if capacity_int < 1:
                raise ValueError
        except (ValueError, TypeError):
            messages.error(request, 'Capacity must be a positive integer.')
            return render(request, 'admin/add_venue.html',
                          {'venue_type_choices': Venue.VENUE_TYPE_CHOICES})

        if Venue.objects.filter(venue_name__iexact=venue_name).exists():
            messages.error(request, f'A venue named "{venue_name}" already exists.')
            return render(request, 'admin/add_venue.html',
                          {'venue_type_choices': Venue.VENUE_TYPE_CHOICES})

        Venue.objects.create(
            venue_name=venue_name,
            venue_type=venue_type,
            capacity=capacity_int,
            location=location,
            facilities=facilities,
            picture=picture,
            is_active=True,
        )

        messages.success(request, f'Venue "{venue_name}" added successfully.')
        return redirect('admin_manage_venues')

    return render(request, 'admin/add_venue.html',
                  {'venue_type_choices': Venue.VENUE_TYPE_CHOICES})


@login_required
def admin_update_venue(request, venue_id):
    if request.user.userprofile.user_type != 'admin':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    venue = get_object_or_404(Venue, id=venue_id)
    
    ctx_base = {'venue': venue, 'venue_type_choices': Venue.VENUE_TYPE_CHOICES}

    if request.method == 'POST':
        venue_name = request.POST.get('venue_name', '').strip()
        venue_type = request.POST.get('venue_type', venue.venue_type).strip()
        capacity   = request.POST.get('capacity')
        location   = request.POST.get('location', '').strip()

        if not all([venue_name, capacity, location]):
            messages.error(request, 'Venue name, capacity, and location are required.')
            return render(request, 'admin/update_venue.html', ctx_base)

        try:
            capacity_int = int(capacity)
            if capacity_int < 1:
                raise ValueError
        except (ValueError, TypeError):
            messages.error(request, 'Capacity must be a positive integer.')
            return render(request, 'admin/update_venue.html', ctx_base)

        venue.venue_name = venue_name
        venue.venue_type = venue_type
        venue.capacity   = capacity_int
        venue.location   = location
        venue.facilities = request.POST.get('facilities', '')

        picture = request.FILES.get('picture')
        if picture:
            venue.picture = picture

        venue.save()
        messages.success(request, f'Venue "{venue_name}" updated successfully.')
        return redirect('admin_manage_venues')
    
    return render(request, 'admin/update_venue.html', ctx_base)


@login_required
def admin_add_venue_block(request, venue_id):
    """Admin: block a venue on a specific date."""
    if request.user.userprofile.user_type != 'admin':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    venue = get_object_or_404(Venue, id=venue_id)

    if request.method == 'POST':
        date_str = request.POST.get('blocked_date', '').strip()
        reason   = request.POST.get('reason', '').strip()
        if not date_str:
            messages.error(request, 'Please provide a date to block.')
            return redirect('admin_manage_venues')
        try:
            from datetime import date as _date
            bd = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            messages.error(request, 'Invalid date format.')
            return redirect('admin_manage_venues')

        obj, created = VenueBlock.objects.get_or_create(
            venue=venue, blocked_date=bd,
            defaults={'reason': reason, 'created_by': request.user}
        )
        if created:
            messages.success(request, f'{venue.venue_name} blocked on {bd.strftime("%d %b %Y")}.')
        else:
            messages.warning(request, f'{venue.venue_name} is already blocked on that date.')

    return redirect('admin_manage_venues')


@login_required
def admin_delete_venue_block(request, block_id):
    """Admin: remove a venue block."""
    if request.user.userprofile.user_type != 'admin':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    block = get_object_or_404(VenueBlock, id=block_id)
    if request.method == 'POST':
        date_str = block.blocked_date.strftime('%d %b %Y')
        name     = block.venue.venue_name
        block.delete()
        messages.success(request, f'Block removed: {name} on {date_str}.')
    return redirect('admin_manage_venues')


@login_required
def admin_toggle_venue_status(request, venue_id):
    if request.method == 'POST':
        try:
            if not hasattr(request.user, 'userprofile') or request.user.userprofile.user_type != 'admin':
                messages.error(request, 'Access denied. Admin privileges required.')
                return redirect('dashboard')
            
            venue           = get_object_or_404(Venue, id=venue_id)
            venue.is_active = not venue.is_active
            venue.save()
            
            status = "activated" if venue.is_active else "deactivated"
            messages.success(request, f'Venue "{venue.venue_name}" has been {status}!')
        except Exception as e:
            messages.error(request, f'Error toggling venue status: {str(e)}')
    
    return redirect('admin_manage_venues')


@login_required
def admin_delete_venue(request, venue_id):
    if request.user.userprofile.user_type != 'admin':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    venue      = get_object_or_404(Venue, id=venue_id)
    venue_name = venue.venue_name
    
    if request.method == 'POST':
        venue.delete()
        messages.success(request, f'Venue "{venue_name}" has been permanently deleted!')
        return redirect('admin_manage_venues')
    
    messages.error(request, 'Invalid delete request.')
    return redirect('admin_manage_venues')


@login_required
def admin_view_feedback(request):
    if request.user.userprofile.user_type != 'admin':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    venue_filter  = request.GET.get('venue')
    status_filter = request.GET.get('status', 'all')
    
    feedbacks = VenueFeedback.objects.all().select_related(
        'lecturer', 'venue', 'replacement_request'
    ).order_by('-created_at')
    
    if venue_filter:
        feedbacks = feedbacks.filter(venue_id=venue_filter)
    
    if status_filter == 'critical':
        feedbacks = feedbacks.filter(issue_status='critical')
    elif status_filter == 'moderate':
        feedbacks = feedbacks.filter(issue_status='moderate')
    elif status_filter == 'solved':
        feedbacks = feedbacks.filter(issue_status='solved')
    
    venue_issues = VenueFeedback.objects.values(
        'venue__id', 'venue__venue_name'
    ).annotate(
        total_reports=Count('id'),
        critical_issues=Count('id', filter=Q(issue_status='critical')),
        moderate_issues=Count('id', filter=Q(issue_status='moderate')),
        solved=Count('id', filter=Q(issue_status='solved'))
    ).order_by('-critical_issues', '-total_reports')
    
    venues         = Venue.objects.filter(is_active=True)
    critical_count = feedbacks.filter(issue_status='critical').count()
    moderate_count = feedbacks.filter(issue_status='moderate').count()
    solved_count   = feedbacks.filter(issue_status='solved').count()
    
    context = {
        'feedbacks':       feedbacks,
        'venue_issues':    venue_issues,
        'venues':          venues,
        'selected_venue':  venue_filter,
        'selected_status': status_filter,
        'total_reports':   feedbacks.count(),
        'critical_count':  critical_count,
        'moderate_count':  moderate_count,
        'solved_count':    solved_count,
    }
    
    return render(request, 'admin/view_feedback.html', context)


@login_required
def admin_generate_replacement_report(request):
    if request.user.userprofile.user_type != 'admin':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    all_requests = ClassReplacementRequest.objects.all().select_related(
        'lecturer', 'lecturer__userprofile',
        'subject', 'subject__semester',
        'venue', 'approved_by'
    ).order_by('-created_at')
    
    status_filter   = request.GET.get('status', '')
    date_from       = request.GET.get('date_from', '')
    date_to         = request.GET.get('date_to', '')
    lecturer_filter = request.GET.get('lecturer', '')
    subject_filter  = request.GET.get('subject', '')
    venue_filter    = request.GET.get('venue', '')
    semester_filter = request.GET.get('semester', '')
    search_query    = request.GET.get('search', '')
    
    if status_filter:
        all_requests = all_requests.filter(status=status_filter)
    if date_from:
        try:
            all_requests = all_requests.filter(created_at__date__gte=datetime.strptime(date_from, '%Y-%m-%d').date())
        except ValueError:
            pass
    if date_to:
        try:
            all_requests = all_requests.filter(created_at__date__lte=datetime.strptime(date_to, '%Y-%m-%d').date())
        except ValueError:
            pass
    if lecturer_filter:
        all_requests = all_requests.filter(lecturer_id=lecturer_filter)
    if subject_filter:
        all_requests = all_requests.filter(subject_id=subject_filter)
    if venue_filter:
        all_requests = all_requests.filter(venue_id=venue_filter)
    if semester_filter:
        all_requests = all_requests.filter(subject__semester_id=semester_filter)
    if search_query:
        all_requests = all_requests.filter(
            Q(lecturer__username__icontains=search_query) |
            Q(lecturer__first_name__icontains=search_query) |
            Q(lecturer__last_name__icontains=search_query) |
            Q(subject__subject_code__icontains=search_query) |
            Q(subject__subject_name__icontains=search_query) |
            Q(venue__venue_name__icontains=search_query) |
            Q(reason__icontains=search_query)
        )
    
    total_requests    = all_requests.count()
    approved_requests = all_requests.filter(status='approved').count()
    pending_requests  = all_requests.filter(status='pending').count()
    rejected_requests = all_requests.filter(status='rejected').count()
    approval_rate     = (approved_requests / total_requests * 100) if total_requests > 0 else 0
    
    requests_by_lecturer = all_requests.values(
        'lecturer__username', 'lecturer__first_name', 'lecturer__last_name'
    ).annotate(
        total=Count('id'),
        approved=Count('id', filter=Q(status='approved')),
        pending=Count('id', filter=Q(status='pending')),
        rejected=Count('id', filter=Q(status='rejected'))
    ).order_by('-total')[:10]
    
    requests_by_subject = all_requests.values(
        'subject__subject_code', 'subject__subject_name'
    ).annotate(count=Count('id')).order_by('-count')[:10]
    
    requests_by_venue = all_requests.values(
        'venue__venue_name'
    ).annotate(count=Count('id')).order_by('-count')[:10]
    
    six_months_ago = timezone.now() - timedelta(days=180)
    monthly_trend = all_requests.filter(
        created_at__gte=six_months_ago
    ).extra(
        select={'month': "strftime('%%Y-%%m', created_at)"}
    ).values('month').annotate(
        total=Count('id'),
        approved=Count('id', filter=Q(status='approved')),
        rejected=Count('id', filter=Q(status='rejected'))
    ).order_by('month')
    
    lecturers = User.objects.filter(userprofile__user_type='lecturer').order_by('first_name', 'last_name')
    subjects  = Subject.objects.all().order_by('subject_code')
    venues    = Venue.objects.all().order_by('venue_name')
    semesters = Semester.objects.all().order_by('-start_date')
    
    context = {
        'all_requests':          all_requests,
        'total_requests':        total_requests,
        'approved_requests':     approved_requests,
        'pending_requests':      pending_requests,
        'rejected_requests':     rejected_requests,
        'approval_rate':         approval_rate,
        'requests_by_lecturer':  requests_by_lecturer,
        'requests_by_subject':   requests_by_subject,
        'requests_by_venue':     requests_by_venue,
        'monthly_trend':         monthly_trend,
        'lecturers':             lecturers,
        'subjects':              subjects,
        'venues':                venues,
        'semesters':             semesters,
        'current_status':        status_filter,
        'current_date_from':     date_from,
        'current_date_to':       date_to,
        'current_lecturer':      lecturer_filter,
        'current_subject':       subject_filter,
        'current_venue':         venue_filter,
        'current_semester':      semester_filter,
        'current_search':        search_query,
    }
    
    return render(request, 'admin/replacement_report.html', context)


@login_required
def export_feedback_report_csv(request):
    if request.user.userprofile.user_type != 'admin':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    feedbacks = VenueFeedback.objects.all().select_related('lecturer', 'venue').order_by('-created_at')
    
    issue_status_filter = request.GET.get('issue_status', '')
    venue_filter        = request.GET.get('venue', '')
    lecturer_filter     = request.GET.get('lecturer', '')
    search_query        = request.GET.get('search', '')
    date_from           = request.GET.get('date_from', '')
    date_to             = request.GET.get('date_to', '')
    
    if issue_status_filter:
        feedbacks = feedbacks.filter(issue_status=issue_status_filter)
    if venue_filter:
        feedbacks = feedbacks.filter(venue_id=venue_filter)
    if lecturer_filter:
        feedbacks = feedbacks.filter(lecturer_id=lecturer_filter)
    if search_query:
        feedbacks = feedbacks.filter(
            Q(venue__venue_name__icontains=search_query) |
            Q(venue__location__icontains=search_query) |
            Q(lecturer__first_name__icontains=search_query) |
            Q(lecturer__last_name__icontains=search_query) |
            Q(feedback_text__icontains=search_query)
        )
    if date_from:
        try:
            feedbacks = feedbacks.filter(created_at__date__gte=datetime.strptime(date_from, '%Y-%m-%d').date())
        except ValueError:
            pass
    if date_to:
        try:
            feedbacks = feedbacks.filter(created_at__date__lte=datetime.strptime(date_to, '%Y-%m-%d').date())
        except ValueError:
            pass
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="venue_issues_report.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['ID', 'Lecturer', 'Venue', 'Location', 'Issue Status', 'Feedback', 'Created At'])
    
    for feedback in feedbacks:
        writer.writerow([
            feedback.id,
            feedback.lecturer.get_full_name(),
            feedback.venue.venue_name,
            feedback.venue.location,
            feedback.get_issue_status_display(),
            feedback.feedback_text,
            feedback.created_at.strftime('%Y-%m-%d %H:%M:%S')
        ])
    
    return response


@login_required
def export_replacement_report_csv(request):
    if request.user.userprofile.user_type != 'admin':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    requests_query = ClassReplacementRequest.objects.all().select_related(
        'lecturer', 'subject', 'venue', 'approved_by'
    ).order_by('-created_at')
    
    search      = request.GET.get('search', '')
    status      = request.GET.get('status', '')
    lecturer_id = request.GET.get('lecturer', '')
    subject_id  = request.GET.get('subject', '')
    venue_id    = request.GET.get('venue', '')
    semester_id = request.GET.get('semester', '')
    date_from   = request.GET.get('date_from', '')
    date_to     = request.GET.get('date_to', '')
    
    if search:
        requests_query = requests_query.filter(
            Q(lecturer__first_name__icontains=search) |
            Q(lecturer__last_name__icontains=search) |
            Q(subject__subject_code__icontains=search) |
            Q(subject__subject_name__icontains=search) |
            Q(venue__venue_name__icontains=search)
        )
    if status:
        requests_query = requests_query.filter(status=status)
    if lecturer_id:
        requests_query = requests_query.filter(lecturer_id=lecturer_id)
    if subject_id:
        requests_query = requests_query.filter(subject_id=subject_id)
    if venue_id:
        requests_query = requests_query.filter(venue_id=venue_id)
    if semester_id:
        requests_query = requests_query.filter(subject__semester_id=semester_id)
    if date_from:
        requests_query = requests_query.filter(original_date__gte=date_from)
    if date_to:
        requests_query = requests_query.filter(original_date__lte=date_to)
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="replacement_report.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'ID', 'Lecturer', 'Subject Code', 'Subject Name',
        'Original Date', 'Original Time', 'Replacement Date',
        'Replacement Time', 'Venue', 'Status', 'Reason',
        'Approved By', 'Created At'
    ])
    
    for req in requests_query:
        writer.writerow([
            req.id,
            req.lecturer.get_full_name(),
            req.subject.subject_code,
            req.subject.subject_name,
            req.original_date.strftime('%Y-%m-%d') if req.original_date else '',
            req.original_time_slot,
            req.replacement_date.strftime('%Y-%m-%d') if req.replacement_date else '',
            req.replacement_time_slot,
            req.venue.venue_name,
            req.status.upper(),
            req.reason,
            req.approved_by.get_full_name() if req.approved_by else 'N/A',
            req.created_at.strftime('%Y-%m-%d %H:%M:%S')
        ])
    
    return response


@login_required
def admin_generate_feedback_report(request):
    if request.user.userprofile.user_type != 'admin':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    feedbacks = VenueFeedback.objects.all().select_related(
        'lecturer', 'lecturer__userprofile', 'venue'
    ).order_by('-created_at')
    
    issue_status_filter = request.GET.get('issue_status', '')
    date_from           = request.GET.get('date_from', '')
    date_to             = request.GET.get('date_to', '')
    venue_filter        = request.GET.get('venue', '')
    lecturer_filter     = request.GET.get('lecturer', '')
    search_query        = request.GET.get('search', '')
    
    if issue_status_filter:
        feedbacks = feedbacks.filter(issue_status=issue_status_filter)
    if date_from:
        try:
            feedbacks = feedbacks.filter(created_at__date__gte=datetime.strptime(date_from, '%Y-%m-%d').date())
        except ValueError:
            pass
    if date_to:
        try:
            feedbacks = feedbacks.filter(created_at__date__lte=datetime.strptime(date_to, '%Y-%m-%d').date())
        except ValueError:
            pass
    if venue_filter:
        feedbacks = feedbacks.filter(venue_id=venue_filter)
    if lecturer_filter:
        feedbacks = feedbacks.filter(lecturer_id=lecturer_filter)
    if search_query:
        feedbacks = feedbacks.filter(
            Q(venue__venue_name__icontains=search_query) |
            Q(venue__location__icontains=search_query) |
            Q(lecturer__first_name__icontains=search_query) |
            Q(lecturer__last_name__icontains=search_query) |
            Q(feedback_text__icontains=search_query)
        )
    
    total_feedbacks = feedbacks.count()
    moderate_issues = feedbacks.filter(issue_status='moderate').count()
    critical_issues = feedbacks.filter(issue_status='critical').count()
    solved_issues   = feedbacks.filter(issue_status='solved').count()
    
    issue_distribution = feedbacks.values('issue_status').annotate(count=Count('id')).order_by('issue_status')
    
    venue_issues = feedbacks.values('venue__venue_name', 'venue__location').annotate(
        feedback_count=Count('id'),
        moderate_count=Count('id', filter=Q(issue_status='moderate')),
        critical_count=Count('id', filter=Q(issue_status='critical')),
        solved_count=Count('id', filter=Q(issue_status='solved'))
    ).order_by('-critical_count', '-moderate_count')
    
    feedback_by_lecturer = feedbacks.values(
        'lecturer__username', 'lecturer__first_name', 'lecturer__last_name'
    ).annotate(
        count=Count('id'),
        moderate_count=Count('id', filter=Q(issue_status='moderate')),
        critical_count=Count('id', filter=Q(issue_status='critical')),
        solved_count=Count('id', filter=Q(issue_status='solved'))
    ).order_by('-count')[:10]
    
    six_months_ago = timezone.now() - timedelta(days=180)
    monthly_feedback = feedbacks.filter(
        created_at__gte=six_months_ago
    ).extra(
        select={'month': "strftime('%%Y-%%m', created_at)"}
    ).values('month').annotate(
        total=Count('id'),
        moderate=Count('id', filter=Q(issue_status='moderate')),
        critical=Count('id', filter=Q(issue_status='critical')),
        solved=Count('id', filter=Q(issue_status='solved'))
    ).order_by('month')
    
    venues    = Venue.objects.all().order_by('venue_name')
    lecturers = User.objects.filter(userprofile__user_type='lecturer').order_by('first_name', 'last_name')
    
    context = {
        'feedbacks':             feedbacks,
        'total_feedbacks':       total_feedbacks,
        'moderate_issues':       moderate_issues,
        'critical_issues':       critical_issues,
        'solved_issues':         solved_issues,
        'issue_distribution':    issue_distribution,
        'venue_issues':          venue_issues,
        'feedback_by_lecturer':  feedback_by_lecturer,
        'monthly_feedback':      monthly_feedback,
        'venues':                venues,
        'lecturers':             lecturers,
        'current_issue_status':  issue_status_filter,
        'current_date_from':     date_from,
        'current_date_to':       date_to,
        'current_venue':         venue_filter,
        'current_lecturer':      lecturer_filter,
        'current_search':        search_query,
    }
    
    return render(request, 'admin/feedback_report.html', context)


@login_required
def admin_manage_requests(request):
    if request.user.userprofile.user_type != 'admin':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    pending = ClassReplacementRequest.objects.filter(
        status='pending'
    ).select_related('lecturer', 'subject', 'subject__semester', 'venue').order_by('-created_at')
    
    approved = ClassReplacementRequest.objects.filter(
        status='approved'
    ).select_related('lecturer', 'subject', 'subject__semester', 'venue').order_by('-created_at')
    
    rejected = ClassReplacementRequest.objects.filter(
        status='rejected'
    ).select_related('lecturer', 'subject', 'subject__semester', 'venue').order_by('-created_at')
    
    context = {
        'pending':  pending,
        'approved': approved,
        'rejected': rejected,
    }
    
    return render(request, 'admin/manage_requests.html', context)


@login_required
def admin_resolve_feedback(request, pk):
    if not hasattr(request.user, 'userprofile') or request.user.userprofile.user_type != 'admin':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    feedback = get_object_or_404(VenueFeedback, pk=pk)
    
    if request.method == 'POST':
        resolution_notes = request.POST.get('resolution_notes', '')

        feedback.issue_status    = 'solved'
        feedback.is_resolved     = True
        feedback.resolved_by     = request.user
        feedback.resolved_at     = timezone.now()
        feedback.resolution_notes = resolution_notes
        feedback.save()
        notify_issue_resolved(feedback)

        messages.success(request, f'Issue resolved successfully. Venue: {feedback.venue.venue_name}')
        return redirect('admin_view_feedback')
    
    return render(request, 'admin/resolve_feedback.html', {'feedback': feedback})


@login_required
def admin_unresolve_feedback(request, pk):
    if not hasattr(request.user, 'userprofile') or request.user.userprofile.user_type != 'admin':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    feedback = get_object_or_404(VenueFeedback, pk=pk)
    
    feedback.issue_status     = 'moderate'
    feedback.is_resolved      = False
    feedback.resolved_by      = None
    feedback.resolved_at      = None
    feedback.resolution_notes = None
    feedback.save()

    messages.warning(request, f'Issue reopened as moderate. Venue: {feedback.venue.venue_name}')
    return redirect('admin_view_feedback')


# ==================== NOTIFICATION VIEWS ====================

@login_required
def get_notifications(request):
    """AJAX — returns unread notifications for the bell icon."""
    notifs = Notification.objects.filter(
        recipient=request.user, is_read=False
    ).order_by('-created_at')[:10]

    data = [{
        'id':      n.id,
        'title':   n.title,
        'message': n.message[:120],
        'type':    n.notif_type,
        'time':    n.created_at.strftime('%d %b %Y, %H:%M'),
    } for n in notifs]

    return JsonResponse({'notifications': data, 'unread_count': len(data)})


@login_required
def mark_notifications_read(request):
    """AJAX POST — marks all notifications as read."""
    if request.method == 'POST':
        Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
        return JsonResponse({'status': 'ok'})
    return JsonResponse({'error': 'POST required'}, status=405)


@login_required
def mark_single_notification_read(request, pk):
    """AJAX POST — marks one notification as read."""
    if request.method == 'POST':
        Notification.objects.filter(pk=pk, recipient=request.user).update(is_read=True)
        return JsonResponse({'status': 'ok'})
    return JsonResponse({'error': 'POST required'}, status=405)


# ==================== QR CODE ATTENDANCE VIEWS ====================

@login_required
def lecturer_generate_qr(request, request_id):
    """Lecturer generates a QR code for a specific approved replacement class."""
    if not hasattr(request.user, 'userprofile') or request.user.userprofile.user_type != 'lecturer':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    replacement = get_object_or_404(
        ClassReplacementRequest, id=request_id,
        lecturer=request.user, status='approved'
    )

    session, created = AttendanceSession.objects.get_or_create(
        replacement_request=replacement,
        defaults={
            'qr_token':  uuid.uuid4().hex,
            'is_active': True,
            'expires_at': timezone.now() + timedelta(hours=3),
        }
    )

    scan_url = request.build_absolute_uri(f'/attendance/scan/{session.qr_token}/')

    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(scan_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color='black', back_color='white')

    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    qr_b64 = base64.b64encode(buffer.getvalue()).decode()

    attendance_records = AttendanceRecord.objects.filter(
        session=session
    ).select_related('student').order_by('scanned_at')

    context = {
        'replacement':        replacement,
        'session':            session,
        'qr_b64':             qr_b64,
        'scan_url':           scan_url,
        'attendance_records': attendance_records,
        'total_present':      attendance_records.count(),
    }
    return render(request, 'lecturer/qr_attendance.html', context)


@login_required
def lecturer_toggle_qr_session(request, session_id):
    """Activate or deactivate a QR session."""
    session = get_object_or_404(AttendanceSession, id=session_id,
                                replacement_request__lecturer=request.user)
    if request.method == 'POST':
        session.is_active = not session.is_active
        session.save()
        status = 'activated' if session.is_active else 'deactivated'
        messages.success(request, f'QR session {status}.')
    return redirect('lecturer_generate_qr', request_id=session.replacement_request_id)


@login_required
def student_scan_qr(request, token):
    """Student lands here after scanning the QR code."""
    if not hasattr(request.user, 'userprofile') or request.user.userprofile.user_type != 'student':
        messages.error(request, 'Only students can mark attendance.')
        return redirect('dashboard')

    session = get_object_or_404(AttendanceSession, qr_token=token)

    def _session_status():
        if not session.is_active:
            return 'closed'
        if timezone.now() > session.expires_at:
            return 'expired'
        if AttendanceRecord.objects.filter(session=session, student=request.user).exists():
            return 'already'
        return None

    status = _session_status()
    if status:
        return render(request, 'student/scan_qr.html', {'status': status, 'session': session})

    if request.method == 'POST':
        # Re-validate before writing — guards against race between GET confirm and POST submit
        status = _session_status()
        if status:
            return render(request, 'student/scan_qr.html', {'status': status, 'session': session})
        AttendanceRecord.objects.get_or_create(session=session, student=request.user)
        return render(request, 'student/scan_qr.html', {'status': 'success', 'session': session})

    return render(request, 'student/scan_qr.html', {'status': 'confirm', 'session': session})


# ==================== ANALYTICS JSON ENDPOINT (for Chart.js) ====================

@login_required
def admin_chart_data(request):
    """Returns JSON data for Chart.js charts on the admin dashboard."""
    if not hasattr(request.user, 'userprofile') or request.user.userprofile.user_type != 'admin':
        return JsonResponse({'error': 'Access denied'}, status=403)

    from django.db.models.functions import TruncMonth
    from django.db.models import Count, Q

    # Monthly trend — last 6 months
    six_months_ago = timezone.now() - timedelta(days=180)
    monthly = (
        ClassReplacementRequest.objects
        .filter(created_at__gte=six_months_ago)
        .annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(
            total=Count('id'),
            approved=Count('id', filter=Q(status='approved')),
            rejected=Count('id', filter=Q(status='rejected')),
            pending=Count('id', filter=Q(status='pending')),
        )
        .order_by('month')
    )

    monthly_labels   = [m['month'].strftime('%b %Y') for m in monthly]
    monthly_total    = [m['total']    for m in monthly]
    monthly_approved = [m['approved'] for m in monthly]
    monthly_rejected = [m['rejected'] for m in monthly]
    monthly_pending  = [m['pending']  for m in monthly]

    # Status breakdown (donut)
    status_counts = ClassReplacementRequest.objects.aggregate(
        approved=Count('id', filter=Q(status='approved')),
        pending=Count('id',  filter=Q(status='pending')),
        rejected=Count('id', filter=Q(status='rejected')),
    )

    # Top 5 venues by usage
    top_venues = (
        ClassReplacementRequest.objects
        .values('venue__venue_name')
        .annotate(count=Count('id'))
        .order_by('-count')[:5]
    )

    # Top 5 lecturers by request count
    top_lecturers = (
        ClassReplacementRequest.objects
        .values('lecturer__first_name', 'lecturer__last_name')
        .annotate(count=Count('id'))
        .order_by('-count')[:5]
    )

    # Feedback severity breakdown
    from .models import VenueFeedback
    feedback_counts = VenueFeedback.objects.aggregate(
        moderate=Count('id', filter=Q(issue_status='moderate')),
        critical=Count('id', filter=Q(issue_status='critical')),
        solved=Count('id',   filter=Q(issue_status='solved')),
    )

    return JsonResponse({
        'monthly': {
            'labels':   monthly_labels,
            'total':    monthly_total,
            'approved': monthly_approved,
            'rejected': monthly_rejected,
            'pending':  monthly_pending,
        },
        'status_breakdown': status_counts,
        'top_venues': {
            'labels': [v['venue__venue_name'] for v in top_venues],
            'counts': [v['count'] for v in top_venues],
        },
        'top_lecturers': {
            'labels': [f"{l['lecturer__first_name']} {l['lecturer__last_name']}" for l in top_lecturers],
            'counts': [l['count'] for l in top_lecturers],
        },
        'feedback_severity': feedback_counts,
    })


@login_required
def lecturer_chart_data(request):
    """Returns JSON chart data for the lecturer's own request history."""
    if not hasattr(request.user, 'userprofile') or request.user.userprofile.user_type != 'lecturer':
        return JsonResponse({'error': 'Access denied'}, status=403)

    from django.db.models.functions import TruncMonth
    from django.db.models import Count, Q

    six_months_ago = timezone.now() - timedelta(days=180)
    monthly = (
        ClassReplacementRequest.objects
        .filter(lecturer=request.user, created_at__gte=six_months_ago)
        .annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(
            total=Count('id'),
            approved=Count('id', filter=Q(status='approved')),
            pending=Count('id',  filter=Q(status='pending')),
            rejected=Count('id', filter=Q(status='rejected')),
        )
        .order_by('month')
    )

    status_counts = ClassReplacementRequest.objects.filter(lecturer=request.user).aggregate(
        approved=Count('id', filter=Q(status='approved')),
        pending=Count('id',  filter=Q(status='pending')),
        rejected=Count('id', filter=Q(status='rejected')),
    )

    return JsonResponse({
        'monthly': {
            'labels':   [m['month'].strftime('%b %Y') for m in monthly],
            'total':    [m['total']    for m in monthly],
            'approved': [m['approved'] for m in monthly],
            'pending':  [m['pending']  for m in monthly],
            'rejected': [m['rejected'] for m in monthly],
        },
        'status_breakdown': status_counts,
    })


# ==================== PDF EXPORT VIEWS ====================

@login_required
def export_replacement_report_pdf(request):
    if request.user.userprofile.user_type != 'admin':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
    from reportlab.lib.units import cm

    requests_qs = ClassReplacementRequest.objects.all().select_related(
        'lecturer', 'subject', 'venue', 'approved_by'
    ).order_by('-created_at')

    status_filter = request.GET.get('status', '')
    if status_filter:
        requests_qs = requests_qs.filter(status=status_filter)

    buffer   = io.BytesIO()
    doc      = SimpleDocTemplate(buffer, pagesize=landscape(A4),
                                 rightMargin=1.5*cm, leftMargin=1.5*cm,
                                 topMargin=1.5*cm, bottomMargin=1.5*cm)
    styles   = getSampleStyleSheet()
    elements = []

    title_style = ParagraphStyle('Title', parent=styles['Title'],
                                 fontSize=18, textColor=colors.HexColor('#1e3a5f'),
                                 spaceAfter=4)
    sub_style   = ParagraphStyle('Sub', parent=styles['Normal'],
                                 fontSize=10, textColor=colors.grey, spaceAfter=16)

    elements.append(Paragraph('ARIS — Academic Replacement Intelligence System', title_style))
    elements.append(Paragraph(f'Replacement Report — Generated {timezone.now().strftime("%d %b %Y, %H:%M")}', sub_style))
    elements.append(HRFlowable(width='100%', thickness=1, color=colors.HexColor('#3b82f6')))
    elements.append(Spacer(1, 0.4*cm))

    total    = requests_qs.count()
    approved = requests_qs.filter(status='approved').count()
    pending  = requests_qs.filter(status='pending').count()
    rejected = requests_qs.filter(status='rejected').count()

    summary_data = [
        ['Total Requests', 'Approved', 'Pending', 'Rejected', 'Approval Rate'],
        [str(total), str(approved), str(pending), str(rejected),
         f'{(approved/total*100):.1f}%' if total else '0%'],
    ]
    summary_table = Table(summary_data, colWidths=[4*cm]*5)
    summary_table.setStyle(TableStyle([
        ('BACKGROUND',  (0,0), (-1,0), colors.HexColor('#1e3a5f')),
        ('TEXTCOLOR',   (0,0), (-1,0), colors.white),
        ('FONTNAME',    (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE',    (0,0), (-1,0), 10),
        ('ALIGN',       (0,0), (-1,-1), 'CENTER'),
        ('BACKGROUND',  (0,1), (-1,1), colors.HexColor('#ebf0f8')),
        ('FONTSIZE',    (0,1), (-1,1), 13),
        ('FONTNAME',    (0,1), (-1,1), 'Helvetica-Bold'),
        ('TEXTCOLOR',   (0,1), (-1,1), colors.HexColor('#1e3a5f')),
        ('BOX',         (0,0), (-1,-1), 0.5, colors.HexColor('#d1dbe8')),
        ('INNERGRID',   (0,0), (-1,-1), 0.25, colors.HexColor('#e2e8f0')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor('#ebf0f8'), colors.white]),
        ('TOPPADDING',  (0,0), (-1,-1), 8),
        ('BOTTOMPADDING',(0,0), (-1,-1), 8),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 0.5*cm))

    header = ['#', 'Lecturer', 'Subject', 'Original Date', 'Replacement Date', 'Time Slot', 'Venue', 'Status']
    data   = [header]
    for i, r in enumerate(requests_qs[:200], 1):
        status_text = r.status.upper()
        data.append([
            str(i),
            r.lecturer.get_full_name(),
            f'{r.subject.subject_code}',
            r.original_date.strftime('%d/%m/%Y') if r.original_date else '',
            r.replacement_date.strftime('%d/%m/%Y') if r.replacement_date else '',
            r.replacement_time_slot,
            r.venue.venue_name,
            status_text,
        ])

    col_widths = [1*cm, 4*cm, 3.5*cm, 3*cm, 3*cm, 3*cm, 3.5*cm, 2.5*cm]
    main_table = Table(data, colWidths=col_widths, repeatRows=1)
    main_table.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (-1,0), colors.HexColor('#1e3a5f')),
        ('TEXTCOLOR',     (0,0), (-1,0), colors.white),
        ('FONTNAME',      (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE',      (0,0), (-1,-1), 8),
        ('ALIGN',         (0,0), (-1,-1), 'CENTER'),
        ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
        ('ROWBACKGROUNDS',(0,1), (-1,-1), [colors.white, colors.HexColor('#f0f4f8')]),
        ('BOX',           (0,0), (-1,-1), 0.5, colors.HexColor('#d1dbe8')),
        ('INNERGRID',     (0,0), (-1,-1), 0.25, colors.HexColor('#e8edf5')),
        ('TOPPADDING',    (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    elements.append(main_table)

    doc.build(elements)
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="replacement_report.pdf"'
    return response


@login_required
def export_feedback_report_pdf(request):
    if request.user.userprofile.user_type != 'admin':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
    from reportlab.lib.units import cm

    feedbacks = VenueFeedback.objects.all().select_related(
        'lecturer', 'venue'
    ).order_by('-created_at')

    buffer   = io.BytesIO()
    doc      = SimpleDocTemplate(buffer, pagesize=landscape(A4),
                                 rightMargin=1.5*cm, leftMargin=1.5*cm,
                                 topMargin=1.5*cm, bottomMargin=1.5*cm)
    styles   = getSampleStyleSheet()
    elements = []

    title_style = ParagraphStyle('Title', parent=styles['Title'],
                                 fontSize=18, textColor=colors.HexColor('#1e3a5f'), spaceAfter=4)
    sub_style   = ParagraphStyle('Sub', parent=styles['Normal'],
                                 fontSize=10, textColor=colors.grey, spaceAfter=16)

    elements.append(Paragraph('ARIS — Academic Replacement Intelligence System', title_style))
    elements.append(Paragraph(f'Venue Feedback Report — Generated {timezone.now().strftime("%d %b %Y, %H:%M")}', sub_style))
    elements.append(HRFlowable(width='100%', thickness=1, color=colors.HexColor('#1e3a5f')))
    elements.append(Spacer(1, 0.4*cm))

    total    = feedbacks.count()
    critical = feedbacks.filter(issue_status='critical').count()
    moderate = feedbacks.filter(issue_status='moderate').count()
    solved   = feedbacks.filter(issue_status='solved').count()

    summary_data = [
        ['Total Reports', 'Critical', 'Moderate', 'Solved'],
        [str(total), str(critical), str(moderate), str(solved)],
    ]
    summary_table = Table(summary_data, colWidths=[5*cm]*4)
    summary_table.setStyle(TableStyle([
        ('BACKGROUND',  (0,0), (-1,0), colors.HexColor('#1e3a5f')),
        ('TEXTCOLOR',   (0,0), (-1,0), colors.white),
        ('FONTNAME',    (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE',    (0,0), (-1,0), 10),
        ('ALIGN',       (0,0), (-1,-1), 'CENTER'),
        ('BACKGROUND',  (0,1), (-1,1), colors.HexColor('#ebf0f8')),
        ('FONTSIZE',    (0,1), (-1,1), 14),
        ('FONTNAME',    (0,1), (-1,1), 'Helvetica-Bold'),
        ('TEXTCOLOR',   (0,1), (-1,1), colors.HexColor('#1e3a5f')),
        ('BOX',         (0,0), (-1,-1), 0.5, colors.HexColor('#d1dbe8')),
        ('INNERGRID',   (0,0), (-1,-1), 0.25, colors.HexColor('#e2e8f0')),
        ('TOPPADDING',  (0,0), (-1,-1), 8),
        ('BOTTOMPADDING',(0,0), (-1,-1), 8),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 0.5*cm))

    header = ['#', 'Lecturer', 'Venue', 'Location', 'Severity', 'Issue Description', 'Reported At']
    data   = [header]
    for i, f in enumerate(feedbacks[:200], 1):
        data.append([
            str(i),
            f.lecturer.get_full_name(),
            f.venue.venue_name,
            f.venue.location,
            f.get_issue_status_display(),
            f.feedback_text[:80] + ('…' if len(f.feedback_text) > 80 else ''),
            f.created_at.strftime('%d/%m/%Y %H:%M'),
        ])

    col_widths = [1*cm, 3.5*cm, 3*cm, 3*cm, 2.5*cm, 8*cm, 3*cm]
    main_table = Table(data, colWidths=col_widths, repeatRows=1)
    main_table.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (-1,0), colors.HexColor('#1e3a5f')),
        ('TEXTCOLOR',     (0,0), (-1,0), colors.white),
        ('FONTNAME',      (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE',      (0,0), (-1,-1), 8),
        ('ALIGN',         (0,0), (-1,-1), 'CENTER'),
        ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
        ('ROWBACKGROUNDS',(0,1), (-1,-1), [colors.white, colors.HexColor('#f0f4f8')]),
        ('BOX',           (0,0), (-1,-1), 0.5, colors.HexColor('#d1dbe8')),
        ('INNERGRID',     (0,0), (-1,-1), 0.25, colors.HexColor('#d1dbe8')),
        ('TOPPADDING',    (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    elements.append(main_table)

    doc.build(elements)
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="feedback_report.pdf"'
    return response


# ==================== PWA OFFLINE PAGE ====================

def offline_view(request):
    return render(request, 'offline.html')


# ==================== iCAL / CALENDAR EXPORT ====================

@login_required
def export_ical_bookmarks(request):
    """Export student's bookmarked replacement classes as .ics calendar file."""
    if not hasattr(request.user, 'userprofile') or request.user.userprofile.user_type != 'student':
        return HttpResponse('Access denied', status=403)

    bookmarks = ClassReplacementRequest.objects.filter(
        bookmarked_by__student=request.user,
        status='approved'
    ).select_related('subject', 'venue', 'lecturer')

    lines = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        'PRODID:-//ARIS — Academic Replacement Intelligence System//CRS//EN',
        'CALSCALE:GREGORIAN',
        'METHOD:PUBLISH',
        'X-WR-CALNAME:My Replacement Classes',
        'X-WR-TIMEZONE:Asia/Kuala_Lumpur',
    ]

    for r in bookmarks:
        try:
            start_time_str, end_time_str = r.replacement_time_slot.split('-')
            sh, sm = map(int, start_time_str.strip().split(':'))
            eh, em = map(int, end_time_str.strip().split(':'))
        except Exception:
            sh, sm, eh, em = 8, 0, 9, 0

        dt_start = datetime(
            r.replacement_date.year, r.replacement_date.month, r.replacement_date.day,
            sh, sm
        ).strftime('%Y%m%dT%H%M%S')
        dt_end = datetime(
            r.replacement_date.year, r.replacement_date.month, r.replacement_date.day,
            eh, em
        ).strftime('%Y%m%dT%H%M%S')
        dt_stamp = timezone.now().strftime('%Y%m%dT%H%M%SZ')

        summary  = f"{r.subject.subject_code} — Replacement Class"
        location = f"{r.venue.venue_name}, {r.venue.location}"
        desc     = f"Lecturer: {r.lecturer.get_full_name()}\\nSubject: {r.subject.subject_name}\\nReason: {r.reason}"
        uid      = f"crs-{r.id}-{r.replacement_date}@replacementsystem"

        lines += [
            'BEGIN:VEVENT',
            f'UID:{uid}',
            f'DTSTAMP:{dt_stamp}',
            f'DTSTART;TZID=Asia/Kuala_Lumpur:{dt_start}',
            f'DTEND;TZID=Asia/Kuala_Lumpur:{dt_end}',
            f'SUMMARY:{summary}',
            f'LOCATION:{location}',
            f'DESCRIPTION:{desc}',
            'STATUS:CONFIRMED',
            'END:VEVENT',
        ]

    lines.append('END:VCALENDAR')

    response = HttpResponse('\r\n'.join(lines), content_type='text/calendar; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="replacement_classes.ics"'
    return response


@login_required
def export_ical_single(request, pk):
    """Export a single replacement class as .ics (for any user)."""
    r = get_object_or_404(ClassReplacementRequest, pk=pk, status='approved')

    try:
        start_time_str, end_time_str = r.replacement_time_slot.split('-')
        sh, sm = map(int, start_time_str.strip().split(':'))
        eh, em = map(int, end_time_str.strip().split(':'))
    except Exception:
        sh, sm, eh, em = 8, 0, 9, 0

    dt_start = datetime(
        r.replacement_date.year, r.replacement_date.month, r.replacement_date.day, sh, sm
    ).strftime('%Y%m%dT%H%M%S')
    dt_end = datetime(
        r.replacement_date.year, r.replacement_date.month, r.replacement_date.day, eh, em
    ).strftime('%Y%m%dT%H%M%S')
    dt_stamp = timezone.now().strftime('%Y%m%dT%H%M%SZ')

    lines = [
        'BEGIN:VCALENDAR', 'VERSION:2.0',
        'PRODID:-//ARIS — Academic Replacement Intelligence System//CRS//EN',
        'CALSCALE:GREGORIAN', 'METHOD:PUBLISH',
        'X-WR-TIMEZONE:Asia/Kuala_Lumpur',
        'BEGIN:VEVENT',
        f'UID:crs-{r.id}-{r.replacement_date}@replacementsystem',
        f'DTSTAMP:{dt_stamp}',
        f'DTSTART;TZID=Asia/Kuala_Lumpur:{dt_start}',
        f'DTEND;TZID=Asia/Kuala_Lumpur:{dt_end}',
        f'SUMMARY:{r.subject.subject_code} — Replacement Class',
        f'LOCATION:{r.venue.venue_name}, {r.venue.location}',
        f'DESCRIPTION:Lecturer: {r.lecturer.get_full_name()}\\nSubject: {r.subject.subject_name}',
        'STATUS:CONFIRMED',
        'END:VEVENT',
        'END:VCALENDAR',
    ]

    response = HttpResponse('\r\n'.join(lines), content_type='text/calendar; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="replacement_{r.id}.ics"'
    return response


# ==================== VENUE HEATMAP ====================

@login_required
def admin_venue_heatmap(request):
    """Admin view: heatmap of venue usage by day-of-week × time slot."""
    if not hasattr(request.user, 'userprofile') or request.user.userprofile.user_type != 'admin':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    TIME_SLOTS = [
        '08:00-09:00', '09:00-10:00', '10:00-11:00', '11:00-12:00',
        '12:00-13:00', '13:00-14:00', '14:00-15:00', '15:00-16:00',
        '16:00-17:00', '17:00-18:00',
    ]
    DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']

    venues = Venue.objects.filter(is_active=True).order_by('venue_name')

    # Build heatmap data: {venue_id: {day: {slot: count}}}
    approved = ClassReplacementRequest.objects.filter(status='approved').select_related('venue')
    heat = {}
    max_count = 1
    for req in approved:
        vid  = req.venue_id
        day  = req.replacement_date.weekday()  # 0=Mon
        slot = req.replacement_time_slot
        if day > 4:
            continue
        heat.setdefault(vid, {})
        heat[vid].setdefault(day, {})
        heat[vid][day][slot] = heat[vid][day].get(slot, 0) + 1
        max_count = max(max_count, heat[vid][day][slot])

    # Flatten for template: list of {venue, rows: [{slot, cells: [count,...]}]}
    heatmap_data = []
    for venue in venues:
        rows = []
        for slot in TIME_SLOTS:
            cells = []
            for day in range(5):
                count = heat.get(venue.id, {}).get(day, {}).get(slot, 0)
                intensity = int((count / max_count) * 100) if max_count else 0
                cells.append({'count': count, 'intensity': intensity})
            rows.append({'slot': slot, 'cells': cells})
        heatmap_data.append({'venue': venue, 'rows': rows})

    # Also compute overall grid (all venues combined)
    overall_rows = []
    for slot in TIME_SLOTS:
        cells = []
        for day in range(5):
            total = sum(
                heat.get(v.id, {}).get(day, {}).get(slot, 0) for v in venues
            )
            intensity = int((total / (max_count * len(venues) or 1)) * 100)
            cells.append({'count': total, 'intensity': min(intensity, 100)})
        overall_rows.append({'slot': slot, 'cells': cells})

    context = {
        'heatmap_data':  heatmap_data,
        'overall_rows':  overall_rows,
        'day_names':     DAY_NAMES,
        'time_slots':    TIME_SLOTS,
        'venues':        venues,
        'max_count':     max_count,
    }
    return render(request, 'admin/venue_heatmap.html', context)


# ==================== TIMETABLE / CALENDAR VIEW ====================

@login_required
def timetable_view(request):
    """Weekly timetable: regular class schedule + approved replacement classes."""
    import re

    HOUR_SLOTS = list(range(8, 18))   # 08:00 … 17:00  (each row = 1 hour)
    SLOT_KEYS  = [f"{h:02d}:00" for h in HOUR_SLOTS]

    week_offset = int(request.GET.get('week', 0))
    today       = timezone.now().date()
    monday      = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
    week_days   = [monday + timedelta(days=i) for i in range(5)]

    from replacements.models import ClassSchedule

    profile   = getattr(request.user, 'userprofile', None)
    user_type = getattr(profile, 'user_type', 'student')

    # ── 1. Collect regular class schedules ───────────────────────────────────
    if user_type == 'student':
        enrolled_sems = list(Semester.objects.filter(enrollments__student=request.user))
        regular_qs = ClassSchedule.objects.filter(
            subject__semester__in=enrolled_sems,
        ).select_related('subject', 'subject__semester', 'subject__lecturer')
    elif user_type == 'lecturer':
        regular_qs = ClassSchedule.objects.filter(
            subject__lecturer=request.user,
        ).select_related('subject', 'subject__semester')
        enrolled_sems = []
    else:  # admin
        regular_qs = ClassSchedule.objects.all().select_related(
            'subject', 'subject__semester', 'subject__lecturer'
        )
        enrolled_sems = []

    # ── 2. Collect approved replacement requests ──────────────────────────────
    def parse_slot_start(slot_str):
        """Return (start_hour, duration_hours) from various time slot formats."""
        slot_str = slot_str.strip()
        # "08:00-10:00" or "8:00-10:00"
        m = re.match(r'(\d{1,2}):(\d{2})\s*[-–]\s*(\d{1,2}):(\d{2})$', slot_str)
        if m:
            sh, sm, eh, em = int(m.g(1)), int(m.g(2)), int(m.g(3)), int(m.g(4))
            return sh, eh - sh
        # "8:00 AM - 10:00 AM"
        m = re.match(
            r'(\d{1,2}):(\d{2})\s*(AM|PM)\s*[-–]\s*(\d{1,2}):(\d{2})\s*(AM|PM)',
            slot_str, re.IGNORECASE
        )
        if m:
            sh = int(m.group(1))
            if m.group(3).upper() == 'PM' and sh != 12: sh += 12
            eh = int(m.group(4))
            if m.group(6).upper() == 'PM' and eh != 12: eh += 12
            return sh, max(1, eh - sh)
        # fallback: just parse first hour
        m2 = re.match(r'(\d{1,2}):', slot_str)
        if m2:
            sh = int(m2.group(1))
            return sh, 2   # assume 2h default
        return None, 1

    # monkey-patch the re.Match object (typo fix in parse_slot_start)
    import re as _re
    def _parse_slot_start(slot_str):
        slot_str = slot_str.strip()
        m = _re.match(r'(\d{1,2}):(\d{2})\s*[-–]\s*(\d{1,2}):(\d{2})$', slot_str)
        if m:
            sh, eh = int(m.group(1)), int(m.group(3))
            return sh, max(1, eh - sh)
        m = _re.match(
            r'(\d{1,2}):(\d{2})\s*(AM|PM)\s*[-–]\s*(\d{1,2}):(\d{2})\s*(AM|PM)',
            slot_str, _re.IGNORECASE
        )
        if m:
            sh = int(m.group(1))
            if m.group(3).upper() == 'PM' and sh != 12: sh += 12
            eh = int(m.group(4))
            if m.group(6).upper() == 'PM' and eh != 12: eh += 12
            return sh, max(1, eh - sh)
        m2 = _re.match(r'(\d{1,2}):', slot_str)
        if m2:
            return int(m2.group(1)), 2
        return 8, 2

    if user_type == 'student':
        repl_qs = ClassReplacementRequest.objects.filter(
            status='approved',
            replacement_date__in=week_days,
            subject__semester__in=enrolled_sems,
        ).select_related('subject', 'venue', 'lecturer')
    elif user_type == 'lecturer':
        repl_qs = ClassReplacementRequest.objects.filter(
            status='approved',
            replacement_date__in=week_days,
            lecturer=request.user,
        ).select_related('subject', 'venue', 'lecturer')
    else:
        repl_qs = ClassReplacementRequest.objects.filter(
            status='approved',
            replacement_date__in=week_days,
        ).select_related('subject', 'venue', 'lecturer')

    # ── 3. Build base grid {slot_key: {day: []}} ─────────────────────────────
    grid = {k: {d: [] for d in week_days} for k in SLOT_KEYS}
    skip = set()   # (slot_key, day_str) to omit from rendering

    def _add_block(slot_key, day, item, duration):
        if slot_key not in grid or day not in grid[slot_key]:
            return
        grid[slot_key][day].append({'duration': duration, **item})
        # Mark later slots as skip (they'll be covered by rowspan)
        start_h = int(slot_key[:2])
        for dh in range(1, duration):
            sk = f"{start_h + dh:02d}:00"
            if sk in grid:
                skip.add((sk, day.strftime('%Y-%m-%d')))

    # Regular classes (day_of_week → actual date in the week)
    for sched in regular_qs:
        if sched.day_of_week > 4:
            continue
        day      = week_days[sched.day_of_week]
        slot_key = f"{sched.start_time.hour:02d}:00"
        dur      = max(1, sched.end_time.hour - sched.start_time.hour)
        _add_block(slot_key, day, {
            'type':      'regular',
            'code':      sched.subject.subject_code,
            'name':      sched.subject.subject_name,
            'lecturer':  sched.subject.lecturer.get_full_name() if sched.subject.lecturer else '—',
            'sem':       str(sched.subject.semester),
            'start':     sched.start_time.strftime('%H:%M'),
            'end':       sched.end_time.strftime('%H:%M'),
        }, dur)

    # Replacement classes
    for r in repl_qs:
        sh, dur = _parse_slot_start(r.replacement_time_slot)
        slot_key = f"{sh:02d}:00"
        _add_block(slot_key, r.replacement_date, {
            'type':         'replacement',
            'code':         r.subject.subject_code,
            'name':         r.subject.subject_name,
            'lecturer':     r.lecturer.get_full_name(),
            'venue':        r.venue.venue_name,
            'original_date':r.original_date.strftime('%d %b %Y'),
            'original_slot':r.original_time_slot,
            'start':        f"{sh:02d}:00",
            'end':          f"{sh + dur:02d}:00",
            'req_id':       r.id,
        }, dur)

    # ── 4. Serialise grid into rows for the template ──────────────────────────
    rows = []
    for sk in SLOT_KEYS:
        row = [{'type': 'time', 'label': sk}]
        for day in week_days:
            day_str = day.strftime('%Y-%m-%d')
            if (sk, day_str) in skip:
                row.append({'type': 'skip'})
            else:
                items = grid[sk][day]
                rowspan = max((it['duration'] for it in items), default=1)
                row.append({
                    'type':     'cell',
                    'items':    items,
                    'rowspan':  rowspan,
                    'is_today': day == today,
                    'is_empty': len(items) == 0,
                })
        rows.append(row)

    context = {
        'rows':        rows,
        'week_days':   week_days,
        'week_offset': week_offset,
        'today':       today,
        'monday':      monday,
        'user_type':   user_type,
    }
    return render(request, 'timetable.html', context)


# ==================== LECTURER — MY CLASSES ====================

@login_required
def lecturer_my_classes(request):
    """
    Shows all subjects assigned to the lecturer, grouped by semester,
    plus upcoming replacement classes summary.
    """
    if not hasattr(request.user, 'userprofile') or request.user.userprofile.user_type != 'lecturer':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    today = tz.localdate()

    # All subjects this lecturer teaches
    my_subjects = (
        Subject.objects
        .filter(lecturer=request.user)
        .select_related('semester')
        .prefetch_related('schedules')
        .order_by('semester__name', 'semester__class_name', 'subject_code')
    )

    # Group by semester
    from collections import defaultdict
    sem_map = defaultdict(list)
    for subj in my_subjects:
        sem_map[subj.semester].append(subj)
    grouped = sorted(sem_map.items(), key=lambda x: (x[0].name, x[0].class_name))

    # Upcoming replacement classes (pending + approved, date >= today)
    upcoming_replacements = (
        ClassReplacementRequest.objects
        .filter(lecturer=request.user, replacement_date__gte=today)
        .exclude(status='rejected')
        .select_related('subject', 'subject__semester', 'venue')
        .order_by('replacement_date')[:10]
    )

    return render(request, 'lecturer/my_classes.html', {
        'grouped':              grouped,
        'my_subjects':          my_subjects,
        'upcoming_replacements': upcoming_replacements,
        'today':                today,
    })


@login_required
def lecturer_class_timetable(request, sem_id):
    """
    Shows the full weekly timetable for a class group (all subjects, not just
    the lecturer's own). Lecturer must teach at least one subject in that semester.
    """
    import re as _re

    if not hasattr(request.user, 'userprofile') or request.user.userprofile.user_type != 'lecturer':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    semester = get_object_or_404(Semester, pk=sem_id)

    # Security: lecturer must teach at least one subject in this semester
    teaches_here = Subject.objects.filter(lecturer=request.user, semester=semester).exists()
    if not teaches_here:
        messages.error(request, 'You are not assigned to any subject in this class group.')
        return redirect('lecturer_my_classes')

    HOUR_SLOTS = list(range(8, 18))
    SLOT_KEYS  = [f"{h:02d}:00" for h in HOUR_SLOTS]

    week_offset = int(request.GET.get('week', 0))
    today       = tz.localdate()
    monday      = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
    week_days   = [monday + timedelta(days=i) for i in range(5)]

    # All class schedules for this semester
    regular_qs = (
        ClassSchedule.objects
        .filter(subject__semester=semester)
        .select_related('subject', 'subject__lecturer', 'venue')
        .order_by('day_of_week', 'start_time')
    )

    # Approved replacements for this semester in the selected week
    repl_qs = (
        ClassReplacementRequest.objects
        .filter(
            status='approved',
            replacement_date__in=week_days,
            subject__semester=semester,
        )
        .select_related('subject', 'venue', 'lecturer')
    )

    # Build grid (same logic as timetable_view)
    def _parse_slot(slot_str):
        m = _re.match(r'(\d{1,2}):(\d{2})\s*[-–]\s*(\d{1,2}):(\d{2})$', slot_str.strip())
        if m:
            return int(m.group(1)), max(1, int(m.group(3)) - int(m.group(1)))
        m = _re.match(r'(\d{1,2}):(\d{2})\s*(AM|PM)\s*[-–]\s*(\d{1,2}):(\d{2})\s*(AM|PM)',
                       slot_str.strip(), _re.I)
        if m:
            sh = int(m.group(1))
            if m.group(3).upper() == 'PM' and sh != 12: sh += 12
            eh = int(m.group(4))
            if m.group(6).upper() == 'PM' and eh != 12: eh += 12
            return sh, max(1, eh - sh)
        mm = _re.match(r'(\d{1,2}):', slot_str.strip())
        return (int(mm.group(1)), 2) if mm else (8, 2)

    grid = {k: {d: [] for d in week_days} for k in SLOT_KEYS}
    skip = set()

    def _add(sk, day, item, dur):
        if sk not in grid or day not in grid[sk]:
            return
        grid[sk][day].append({'duration': dur, **item})
        sh = int(sk[:2])
        for dh in range(1, dur):
            nk = f"{sh + dh:02d}:00"
            if nk in grid:
                skip.add((nk, day.strftime('%Y-%m-%d')))

    for sched in regular_qs:
        if sched.day_of_week > 4:
            continue
        day = week_days[sched.day_of_week]
        sk  = f"{sched.start_time.hour:02d}:00"
        dur = max(1, sched.end_time.hour - sched.start_time.hour)
        is_mine = sched.subject.lecturer_id == request.user.id
        _add(sk, day, {
            'type':     'regular',
            'code':     sched.subject.subject_code,
            'name':     sched.subject.subject_name,
            'lecturer': sched.subject.lecturer.get_full_name() if sched.subject.lecturer else '—',
            'is_mine':  is_mine,
            'sem':      str(sched.subject.semester),
            'start':    sched.start_time.strftime('%H:%M'),
            'end':      sched.end_time.strftime('%H:%M'),
        }, dur)

    for r in repl_qs:
        sh, dur = _parse_slot(r.replacement_time_slot)
        sk = f"{sh:02d}:00"
        is_mine = r.lecturer_id == request.user.id
        _add(sk, r.replacement_date, {
            'type':          'replacement',
            'code':          r.subject.subject_code,
            'name':          r.subject.subject_name,
            'lecturer':      r.lecturer.get_full_name(),
            'is_mine':       is_mine,
            'venue':         r.venue.venue_name,
            'original_date': r.original_date.strftime('%d %b %Y'),
            'original_slot': r.original_time_slot,
            'start':         f"{sh:02d}:00",
            'end':           f"{sh + dur:02d}:00",
            'req_id':        r.id,
        }, dur)

    rows = []
    for sk in SLOT_KEYS:
        row = [{'type': 'time', 'label': sk}]
        for day in week_days:
            day_str = day.strftime('%Y-%m-%d')
            if (sk, day_str) in skip:
                row.append({'type': 'skip'})
            else:
                items   = grid[sk][day]
                rowspan = max((it['duration'] for it in items), default=1)
                row.append({
                    'type':     'cell',
                    'items':    items,
                    'rowspan':  rowspan,
                    'is_today': day == today,
                    'is_empty': len(items) == 0,
                })
        rows.append(row)

    # All semesters the lecturer teaches (for the sidebar switcher)
    my_semesters = (
        Semester.objects
        .filter(subject__lecturer=request.user)
        .distinct()
        .order_by('name', 'class_name')
    )

    return render(request, 'lecturer/class_timetable.html', {
        'semester':    semester,
        'rows':        rows,
        'week_days':   week_days,
        'week_offset': week_offset,
        'today':       today,
        'monday':      monday,
        'my_semesters': my_semesters,
    })


# ==================== ADMIN — SEMESTER LECTURER ASSIGNMENT ====================

@login_required
def admin_semester_assign(request, sem_id):
    """
    Roster page: admin can assign a lecturer to each subject in a semester.
    """
    if not _admin_guard(request):
        return redirect('dashboard')

    semester  = get_object_or_404(Semester, pk=sem_id)
    subjects  = Subject.objects.filter(semester=semester).select_related('lecturer').order_by('subject_code')
    lecturers = User.objects.filter(userprofile__user_type='lecturer').select_related('userprofile').order_by('last_name', 'first_name')

    if request.method == 'POST':
        updated = 0
        for subj in subjects:
            key   = f'lecturer_{subj.id}'
            value = request.POST.get(key, '').strip()
            new_lecturer = None
            if value:
                try:
                    new_lecturer = User.objects.get(pk=int(value))
                except (User.DoesNotExist, ValueError):
                    pass
            if subj.lecturer != new_lecturer:
                subj.lecturer = new_lecturer
                subj.save(update_fields=['lecturer'])
                updated += 1

        if updated:
            messages.success(request, f'{updated} subject assignment(s) updated.')
        else:
            messages.info(request, 'No changes were made.')
        return redirect('admin_semester_assign', sem_id=sem_id)

    return render(request, 'admin/semester_assign.html', {
        'semester':  semester,
        'subjects':  subjects,
        'lecturers': lecturers,
    })


# ==================== AI CHATBOT ====================

@login_required
def chatbot_view(request):
    """Render the chatbot page (for students)."""
    return render(request, 'student/chatbot.html')


@login_required
def chatbot_api(request):
    """AJAX endpoint — answers questions about replacement classes."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    import json
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    raw_message = body.get('message', '').strip()
    message     = raw_message.lower()

    if not message:
        return JsonResponse({'reply': 'Please type a question!'})

    user      = request.user
    today     = timezone.now().date()
    tomorrow  = today + timedelta(days=1)
    week_start = today - timedelta(days=today.weekday())
    week_end   = week_start + timedelta(days=4)
    user_type  = getattr(getattr(user, 'userprofile', None), 'user_type', 'student')

    reply = None

    # ── Intent: today ─────────────────────────────────────────────────────────
    if any(k in message for k in ["today's", "today"]) and 'tomorrow' not in message:
        qs = ClassReplacementRequest.objects.filter(
            status='approved', replacement_date=today
        ).select_related('subject', 'venue', 'lecturer').order_by('replacement_time_slot')
        if qs:
            lines = [f"**Today's replacement classes ({today.strftime('%A, %d %b %Y')}):**\n"]
            for r in qs:
                lines.append(
                    f"• {r.replacement_time_slot} — **{r.subject.subject_code}** {r.subject.subject_name}\n"
                    f"  {r.lecturer.get_full_name()} | {r.venue.venue_name}"
                )
            reply = '\n'.join(lines)
        else:
            reply = f"No replacement classes scheduled for today ({today.strftime('%A, %d %b %Y')})."

    # ── Intent: tomorrow ──────────────────────────────────────────────────────
    elif any(k in message for k in ["tomorrow's", 'tomorrow']):
        qs = ClassReplacementRequest.objects.filter(
            status='approved', replacement_date=tomorrow
        ).select_related('subject', 'venue', 'lecturer').order_by('replacement_time_slot')
        if qs:
            lines = [f"**Tomorrow's replacement classes ({tomorrow.strftime('%A, %d %b %Y')}):**\n"]
            for r in qs:
                lines.append(
                    f"• {r.replacement_time_slot} — **{r.subject.subject_code}** {r.subject.subject_name}\n"
                    f"  {r.lecturer.get_full_name()} | {r.venue.venue_name}"
                )
            reply = '\n'.join(lines)
        else:
            reply = f"No replacement classes scheduled for tomorrow ({tomorrow.strftime('%A, %d %b %Y')})."

    # ── Intent: this week ─────────────────────────────────────────────────────
    elif any(k in message for k in ['this week', 'week']):
        qs = ClassReplacementRequest.objects.filter(
            status='approved',
            replacement_date__gte=week_start,
            replacement_date__lte=week_end,
        ).select_related('subject', 'venue', 'lecturer').order_by('replacement_date', 'replacement_time_slot')
        if qs:
            lines = [
                f"**This week's replacement classes "
                f"({week_start.strftime('%d %b')} – {week_end.strftime('%d %b %Y')}):**\n"
            ]
            current_day = None
            for r in qs:
                day_label = r.replacement_date.strftime('%A, %d %b')
                if day_label != current_day:
                    lines.append(f"\n**{day_label}**")
                    current_day = day_label
                lines.append(
                    f"• {r.replacement_time_slot} — **{r.subject.subject_code}** | {r.venue.venue_name}"
                )
            reply = '\n'.join(lines)
        else:
            reply = (
                f"No replacement classes this week "
                f"({week_start.strftime('%d %b')} – {week_end.strftime('%d %b')})."
            )

    # ── Intent: upcoming / next / schedule ────────────────────────────────────
    elif any(k in message for k in ['upcoming', 'next', 'soon', 'schedule', 'coming']):
        qs = ClassReplacementRequest.objects.filter(
            status='approved', replacement_date__gte=today
        ).select_related('subject', 'venue', 'lecturer').order_by('replacement_date', 'replacement_time_slot')[:6]
        if qs:
            lines = ['**Upcoming replacement classes:**\n']
            for r in qs:
                lines.append(
                    f"• **{r.replacement_date.strftime('%a, %d %b')}** {r.replacement_time_slot} — "
                    f"**{r.subject.subject_code}** | {r.lecturer.get_full_name()} | {r.venue.venue_name}"
                )
            reply = '\n'.join(lines)
        else:
            reply = 'No upcoming replacement classes at the moment. Check back later!'

    # ── Intent: bookmarks ─────────────────────────────────────────────────────
    elif any(k in message for k in ['bookmark', 'saved', 'my class', 'my replacement', 'my bookmarks']):
        if user_type == 'student':
            bmarks = ClassReplacementRequest.objects.filter(
                bookmarked_by__student=user,
                status='approved',
                replacement_date__gte=today,
            ).select_related('subject', 'venue').order_by('replacement_date')[:6]
            if bmarks:
                lines = ['**Your upcoming bookmarked classes:**\n']
                for r in bmarks:
                    lines.append(
                        f"• **{r.replacement_date.strftime('%a, %d %b')}** {r.replacement_time_slot} — "
                        f"**{r.subject.subject_code}** | {r.venue.venue_name}"
                    )
                reply = '\n'.join(lines)
            else:
                reply = (
                    "You have no upcoming bookmarked classes.\n\n"
                    "Visit **Search Replacements** to find and bookmark classes!"
                )
        else:
            reply = "Bookmark tracking is available for students."

    # ── Intent: venues ────────────────────────────────────────────────────────
    elif any(k in message for k in ['venue', 'room', 'location', 'hall', 'lab', 'building', 'where']):
        venues = Venue.objects.filter(is_active=True).order_by('venue_name')[:10]
        lines  = ['**Available venues:**\n']
        for v in venues:
            lines.append(f"• **{v.venue_name}** — {v.location} (Capacity: {v.capacity})")
        reply = '\n'.join(lines)

    # ── Intent: stats / count ─────────────────────────────────────────────────
    elif any(k in message for k in ['how many', 'count', 'total', 'statistic', 'stats']):
        total_upcoming = ClassReplacementRequest.objects.filter(
            status='approved', replacement_date__gte=today
        ).count()
        today_count = ClassReplacementRequest.objects.filter(
            status='approved', replacement_date=today
        ).count()
        week_count = ClassReplacementRequest.objects.filter(
            status='approved',
            replacement_date__gte=week_start,
            replacement_date__lte=week_end,
        ).count()
        def plural(n): return f"{n} class{'es' if n != 1 else ''}"
        reply = (
            f"**Replacement Class Statistics:**\n\n"
            f"• Today: **{plural(today_count)}**\n"
            f"• This week: **{plural(week_count)}**\n"
            f"• All upcoming: **{plural(total_upcoming)}**\n\n"
            f"Use the Search page to explore the full list."
        )

    # ── Intent: my requests (lecturer) ────────────────────────────────────────
    elif user_type == 'lecturer' and any(
        k in message for k in ['my request', 'my submission', 'pending', 'rejected', 'approved', 'my class']
    ):
        status_filter = None
        if 'pending' in message:
            status_filter = 'pending'
        elif 'rejected' in message:
            status_filter = 'rejected'
        elif 'approved' in message:
            status_filter = 'approved'

        qs = ClassReplacementRequest.objects.filter(lecturer=user)
        if status_filter:
            qs = qs.filter(status=status_filter)
        qs = qs.select_related('subject', 'venue').order_by('-created_at')[:6]

        if qs:
            label = status_filter or 'recent'
            lines = [f"**Your {label} requests:**\n"]
            for r in qs:
                status_badge = {'approved': 'Approved', 'rejected': 'Rejected', 'pending': 'Pending'}.get(r.status, r.status.title())
                lines.append(
                    f"• **{r.subject.subject_code}** — {r.replacement_date.strftime('%a, %d %b')} {r.replacement_time_slot}\n"
                    f"  Status: {status_badge} | Venue: {r.venue.venue_name}"
                )
            reply = '\n'.join(lines)
        else:
            label = status_filter or ''
            reply = f"No {label} requests found."

    # ── Intent: help / greeting ───────────────────────────────────────────────
    elif any(k in message for k in ['help', 'hi', 'hello', 'hey', 'what can', 'assist', 'guide', 'how']):
        caps = (
            "**CRS Assistant — What I Can Help With:**\n\n"
            "• **today** — Classes scheduled for today\n"
            "• **tomorrow** — Tomorrow's classes\n"
            "• **this week** — This week's schedule\n"
            "• **upcoming** — Next upcoming classes\n"
            "• **bookmarks** — Your saved classes\n"
            "• **venues** — All available venues\n"
            "• **stats** — Class count summary\n"
        )
        if user_type == 'lecturer':
            caps += (
                "• **my requests** — Your submitted requests\n"
                "• **pending** / **approved** / **rejected** — Filter by status\n"
            )
        caps += "\nOr simply type a subject code, lecturer name, or venue name to search!"
        reply = caps

    # ── Fallback: full-text search ────────────────────────────────────────────
    else:
        results = ClassReplacementRequest.objects.filter(
            status='approved',
            replacement_date__gte=today,
        ).filter(
            Q(subject__subject_name__icontains=raw_message) |
            Q(subject__subject_code__icontains=raw_message) |
            Q(lecturer__first_name__icontains=raw_message) |
            Q(lecturer__last_name__icontains=raw_message) |
            Q(venue__venue_name__icontains=raw_message)
        ).select_related('subject', 'venue', 'lecturer').order_by('replacement_date')[:6]

        if results:
            lines = [f'**Search results for "{raw_message}":**\n']
            for r in results:
                lines.append(
                    f"• **{r.subject.subject_code}** — {r.replacement_date.strftime('%a, %d %b')} {r.replacement_time_slot}\n"
                    f"  {r.lecturer.get_full_name()} | {r.venue.venue_name}"
                )
            reply = '\n'.join(lines)
        else:
            reply = (
                f'No results found for **"{raw_message}"**.\n\n'
                "Try asking about:\n"
                "• **today** / **tomorrow** / **this week** / **upcoming**\n"
                "• **bookmarks** — your saved classes\n"
                "• **venues** — available venues\n"
                "• A subject code like **CS101** or a lecturer's name"
            )

    return JsonResponse({'reply': reply})


# ==================== ADMIN USER MANAGEMENT ====================

def _admin_guard(request):
    """Return True if the caller is an admin, False otherwise (and flash an error)."""
    if not hasattr(request.user, 'userprofile') or request.user.userprofile.user_type != 'admin':
        messages.error(request, 'Access denied.')
        return False
    return True


@login_required
def admin_manage_users(request):
    if not _admin_guard(request):
        return redirect('dashboard')

    from replacements.models import UserProfile as UP
    tab       = request.GET.get('tab', 'students')
    search    = request.GET.get('q', '').strip()
    course    = request.GET.get('course', '').strip()
    class_grp = request.GET.get('class', '').strip()   # e.g. "1A", "6B"

    students_qs  = User.objects.filter(userprofile__user_type='student').select_related('userprofile')
    lecturers_qs = User.objects.filter(userprofile__user_type='lecturer').select_related('userprofile')

    if course:
        students_qs  = students_qs.filter(userprofile__course=course)
        lecturers_qs = lecturers_qs.filter(userprofile__course=course)

    if class_grp:
        # Filter students by the class_name of their enrolled semester
        students_qs = students_qs.filter(
            enrollments__semester__class_name=class_grp
        ).distinct()

    if search:
        sq = Q(first_name__icontains=search) | Q(last_name__icontains=search) | Q(email__icontains=search)
        students_qs  = students_qs.filter(sq | Q(userprofile__student_id__icontains=search))
        lecturers_qs = lecturers_qs.filter(sq | Q(userprofile__employee_id__icontains=search))

    students_qs  = students_qs.order_by('last_name', 'first_name')
    lecturers_qs = lecturers_qs.order_by('last_name', 'first_name')

    # Build list of available class groups (filtered by course if selected)
    sem_qs = Semester.objects.all()
    if course:
        sem_qs = sem_qs.filter(course=course)
    # Get distinct class names, grouped by semester number for ordered display
    class_options = (
        sem_qs.values('name', 'class_name')
              .distinct()
              .order_by('name', 'class_name')
    )

    return render(request, 'admin/manage_users.html', {
        'students':       students_qs,
        'lecturers':      lecturers_qs,
        'tab':            tab,
        'search':         search,
        'course':         course,
        'class_grp':      class_grp,
        'class_options':  class_options,
        'course_choices': UP.COURSE_CHOICES,
    })


@login_required
def admin_add_user(request):
    if not _admin_guard(request):
        return redirect('dashboard')

    if request.method == 'POST':
        user_type  = request.POST.get('user_type', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name  = request.POST.get('last_name', '').strip()
        email      = request.POST.get('email', '').strip()
        id_number  = request.POST.get('id_number', '').strip()
        # Username defaults to the ID number if left blank
        username   = request.POST.get('username', '').strip() or id_number
        password   = request.POST.get('password', '').strip()

        errors = []
        if not all([user_type, first_name, last_name, email, id_number, password]):
            errors.append('All fields are required.')
        if len(password) < 8:
            errors.append('Password must be at least 8 characters.')
        if User.objects.filter(username=username).exists():
            errors.append(f'Username "{username}" is already taken.')
        if User.objects.filter(email=email).exists():
            errors.append(f'Email "{email}" is already in use.')
        if user_type == 'student' and UserProfile.objects.filter(student_id=id_number).exists():
            errors.append(f'Student ID "{id_number}" is already registered.')
        if user_type == 'lecturer' and UserProfile.objects.filter(employee_id=id_number, user_type='lecturer').exists():
            errors.append(f'Employee ID "{id_number}" is already registered.')

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            user = User.objects.create_user(
                username=username, email=email,
                first_name=first_name, last_name=last_name,
                password=password,
            )
            course = request.POST.get('course', '').strip() or None
            if user_type == 'student':
                UserProfile.objects.create(user=user, user_type='student', student_id=id_number, course=course)
            else:
                UserProfile.objects.create(user=user, user_type='lecturer', employee_id=id_number, course=course)
            messages.success(request, f'{user_type.title()} account for {user.get_full_name()} created.')
            return redirect(f"{reverse('admin_manage_users')}?tab={user_type}s")

    return render(request, 'admin/add_edit_user.html', {
        'mode':           'add',
        'tab':            request.GET.get('tab', 'students'),
        'course_choices': UserProfile.COURSE_CHOICES,
    })


@login_required
def admin_edit_user(request, user_id):
    if not _admin_guard(request):
        return redirect('dashboard')

    target  = get_object_or_404(User, pk=user_id)
    profile = get_object_or_404(UserProfile, user=target)

    if profile.user_type == 'admin':
        messages.error(request, 'Admin accounts cannot be edited here.')
        return redirect('admin_manage_users')

    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name  = request.POST.get('last_name', '').strip()
        email      = request.POST.get('email', '').strip()
        id_number  = request.POST.get('id_number', '').strip()

        errors = []
        if not all([first_name, last_name, email, id_number]):
            errors.append('All fields are required.')
        if User.objects.filter(email=email).exclude(pk=user_id).exists():
            errors.append(f'Email "{email}" is already used by another account.')

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            course = request.POST.get('course', '').strip() or None
            target.first_name = first_name
            target.last_name  = last_name
            target.email      = email
            target.save()
            if profile.user_type == 'student':
                profile.student_id = id_number
            else:
                profile.employee_id = id_number
            profile.course = course
            profile.save()
            messages.success(request, f'Account for {target.get_full_name()} updated.')
            return redirect(f"{reverse('admin_manage_users')}?tab={profile.user_type}s")

    id_value = profile.student_id if profile.user_type == 'student' else profile.employee_id
    return render(request, 'admin/add_edit_user.html', {
        'mode':           'edit',
        'target':         target,
        'profile':        profile,
        'id_value':       id_value,
        'tab':            profile.user_type + 's',
        'course_choices': UserProfile.COURSE_CHOICES,
    })


@login_required
def admin_delete_user(request, user_id):
    if not _admin_guard(request):
        return redirect('dashboard')

    target  = get_object_or_404(User, pk=user_id)
    profile = getattr(target, 'userprofile', None)

    if profile and profile.user_type == 'admin':
        messages.error(request, 'Admin accounts cannot be deleted here.')
        return redirect('admin_manage_users')

    if request.method == 'POST':
        utype = profile.user_type if profile else 'user'
        name  = target.get_full_name() or target.username
        target.delete()
        messages.success(request, f'{name} has been removed from the system.')
        return redirect(f"{reverse('admin_manage_users')}?tab={utype}s")

    return render(request, 'admin/confirm_delete_user.html', {
        'target':  target,
        'profile': profile,
    })


@login_required
def admin_reset_password(request, user_id):
    if not _admin_guard(request):
        return redirect('dashboard')

    target = get_object_or_404(User, pk=user_id)
    profile = getattr(target, 'userprofile', None)
    if profile and profile.user_type == 'admin':
        messages.error(request, 'Cannot reset admin passwords here.')
        return redirect('admin_manage_users')

    if request.method == 'POST':
        new_pw = request.POST.get('new_password', '').strip()
        if len(new_pw) < 8:
            messages.error(request, 'Password must be at least 8 characters.')
        else:
            target.set_password(new_pw)
            target.save()
            messages.success(request, f'Password for {target.get_full_name() or target.username} has been reset.')
        utype = profile.user_type if profile else 'student'
        return redirect(f"{reverse('admin_manage_users')}?tab={utype}s")

    return redirect('admin_manage_users')


# ==================== ADMIN SEMESTER MANAGEMENT ====================

@login_required
def admin_manage_semesters(request):
    if not _admin_guard(request):
        return redirect('dashboard')

    course = request.GET.get('course', '').strip()
    semesters = Semester.objects.annotate(
        subject_count=Count('subject', distinct=True),
        student_count=Count('enrollments', distinct=True),
    ).order_by('course', 'name', 'class_name')

    if course:
        semesters = semesters.filter(course=course)

    return render(request, 'admin/manage_semesters.html', {
        'semesters':      semesters,
        'course':         course,
        'course_choices': Semester.COURSE_CHOICES,
    })


@login_required
def admin_add_semester(request):
    if not _admin_guard(request):
        return redirect('dashboard')

    if request.method == 'POST':
        name       = request.POST.get('name', '').strip()
        class_name = request.POST.get('class_name', '').strip()
        course     = request.POST.get('course', 'CS').strip()
        start_date = request.POST.get('start_date', '').strip()
        end_date   = request.POST.get('end_date', '').strip()
        is_active  = request.POST.get('is_active') == 'on'

        if not all([name, class_name, course, start_date, end_date]):
            messages.error(request, 'All fields are required.')
        elif Semester.objects.filter(name=name, class_name=class_name, course=course).exists():
            messages.error(request, f'A semester named "{name} — Class {class_name}" already exists for this course.')
        else:
            sem = Semester.objects.create(
                name=name, class_name=class_name, course=course,
                start_date=start_date, end_date=end_date,
                is_active=is_active,
            )
            messages.success(request, f'Semester "{sem}" created.')
            return redirect('admin_manage_semesters')

    return render(request, 'admin/add_edit_semester.html', {
        'mode':           'add',
        'course_choices': Semester.COURSE_CHOICES,
    })


@login_required
def admin_edit_semester(request, sem_id):
    if not _admin_guard(request):
        return redirect('dashboard')

    sem = get_object_or_404(Semester, pk=sem_id)

    if request.method == 'POST':
        name       = request.POST.get('name', '').strip()
        class_name = request.POST.get('class_name', '').strip()
        course     = request.POST.get('course', 'CS').strip()
        start_date = request.POST.get('start_date', '').strip()
        end_date   = request.POST.get('end_date', '').strip()
        is_active  = request.POST.get('is_active') == 'on'

        if not all([name, class_name, course, start_date, end_date]):
            messages.error(request, 'All fields are required.')
        else:
            sem.name       = name
            sem.class_name = class_name
            sem.course     = course
            sem.start_date = start_date
            sem.end_date   = end_date
            sem.is_active  = is_active
            sem.save()
            messages.success(request, f'Semester "{sem}" updated.')
            return redirect('admin_manage_semesters')

    return render(request, 'admin/add_edit_semester.html', {
        'mode':           'edit',
        'sem':            sem,
        'course_choices': Semester.COURSE_CHOICES,
    })


@login_required
def admin_delete_semester(request, sem_id):
    if not _admin_guard(request):
        return redirect('dashboard')

    sem = get_object_or_404(Semester, pk=sem_id)
    if request.method == 'POST':
        label = str(sem)
        sem.delete()
        messages.success(request, f'Semester "{label}" deleted.')
    return redirect('admin_manage_semesters')


# ==================== ADMIN SUBJECT MANAGEMENT ====================

@login_required
def admin_manage_subjects(request):
    if not _admin_guard(request):
        return redirect('dashboard')

    sem_id  = request.GET.get('semester', '').strip()
    search  = request.GET.get('q', '').strip()
    course  = request.GET.get('course', '').strip()

    semesters = Semester.objects.order_by('course', 'name', 'class_name')
    if course:
        semesters = semesters.filter(course=course)

    subjects = Subject.objects.select_related('semester', 'lecturer', 'lecturer__userprofile')
    if course:
        subjects = subjects.filter(semester__course=course)
    if sem_id:
        subjects = subjects.filter(semester_id=sem_id)
    if search:
        subjects = subjects.filter(
            Q(subject_code__icontains=search) | Q(subject_name__icontains=search)
        )
    subjects = subjects.order_by('semester__course', 'semester__name', 'subject_code')

    return render(request, 'admin/manage_subjects.html', {
        'subjects':          subjects,
        'semesters':         semesters,
        'selected_semester': sem_id,
        'search':            search,
        'course':            course,
        'course_choices':    Semester.COURSE_CHOICES,
    })


@login_required
def admin_add_subject(request):
    if not _admin_guard(request):
        return redirect('dashboard')

    semesters = Semester.objects.order_by('-start_date', 'name')
    lecturers = User.objects.filter(userprofile__user_type='lecturer').order_by('last_name', 'first_name')

    if request.method == 'POST':
        sem_id       = request.POST.get('semester', '').strip()
        subject_code = request.POST.get('subject_code', '').strip().upper()
        subject_name = request.POST.get('subject_name', '').strip()
        description  = request.POST.get('description', '').strip()
        lecturer_id  = request.POST.get('lecturer') or None

        def _safe_int(key, default):
            try:
                v = int(request.POST.get(key, default))
                return max(0, v)
            except (ValueError, TypeError):
                return default

        credit_hours            = _safe_int('credit_hours', 3)
        lecture_hours_per_week  = _safe_int('lecture_hours_per_week', 3)
        tutorial_hours_per_week = _safe_int('tutorial_hours_per_week', 0)
        lab_hours_per_week      = _safe_int('lab_hours_per_week', 0)
        total_weeks             = _safe_int('total_weeks', 14)

        if not all([sem_id, subject_code, subject_name]):
            messages.error(request, 'Semester, subject code, and subject name are required.')
        elif Subject.objects.filter(semester_id=sem_id, subject_code=subject_code).exists():
            messages.error(request, f'Subject code "{subject_code}" already exists in this semester.')
        else:
            sub = Subject.objects.create(
                semester_id=sem_id,
                subject_code=subject_code,
                subject_name=subject_name,
                description=description,
                lecturer_id=lecturer_id,
                credit_hours=credit_hours,
                lecture_hours_per_week=lecture_hours_per_week,
                tutorial_hours_per_week=tutorial_hours_per_week,
                lab_hours_per_week=lab_hours_per_week,
                total_weeks=total_weeks,
            )
            messages.success(request, f'Subject "{sub}" created.')
            return redirect(f"{reverse('admin_manage_subjects')}?semester={sem_id}")

    return render(request, 'admin/add_edit_subject.html', {
        'mode':               'add',
        'semesters':          semesters,
        'lecturers':          lecturers,
        'preselect_semester': request.GET.get('semester', ''),
    })


@login_required
def admin_edit_subject(request, sub_id):
    if not _admin_guard(request):
        return redirect('dashboard')

    sub       = get_object_or_404(Subject, pk=sub_id)
    semesters = Semester.objects.order_by('-start_date', 'name')
    lecturers = User.objects.filter(userprofile__user_type='lecturer').order_by('last_name', 'first_name')

    if request.method == 'POST':
        def _safe_int(key, default):
            try:
                v = int(request.POST.get(key, default))
                return max(0, v)
            except (ValueError, TypeError):
                return default

        sub.semester_id             = request.POST.get('semester') or sub.semester_id
        sub.subject_code            = request.POST.get('subject_code', '').strip().upper()
        sub.subject_name            = request.POST.get('subject_name', '').strip()
        sub.description             = request.POST.get('description', '').strip()
        sub.lecturer_id             = request.POST.get('lecturer') or None
        sub.credit_hours            = _safe_int('credit_hours', sub.credit_hours)
        sub.lecture_hours_per_week  = _safe_int('lecture_hours_per_week', sub.lecture_hours_per_week)
        sub.tutorial_hours_per_week = _safe_int('tutorial_hours_per_week', sub.tutorial_hours_per_week)
        sub.lab_hours_per_week      = _safe_int('lab_hours_per_week', sub.lab_hours_per_week)
        sub.total_weeks             = _safe_int('total_weeks', sub.total_weeks)
        sub.save()
        messages.success(request, f'Subject "{sub}" updated.')
        return redirect(f"{reverse('admin_manage_subjects')}?semester={sub.semester_id}")

    return render(request, 'admin/add_edit_subject.html', {
        'mode':      'edit',
        'sub':       sub,
        'semesters': semesters,
        'lecturers': lecturers,
    })


@login_required
def admin_delete_subject(request, sub_id):
    if not _admin_guard(request):
        return redirect('dashboard')

    sub = get_object_or_404(Subject, pk=sub_id)
    sem_id = sub.semester_id
    if request.method == 'POST':
        sub.delete()
        messages.success(request, 'Subject deleted.')
    return redirect(f"{reverse('admin_manage_subjects')}?semester={sem_id}")


# ==================== ADMIN ENROLLMENT MANAGEMENT ====================

@login_required
def admin_manage_enrollments(request):
    if not _admin_guard(request):
        return redirect('dashboard')

    sem_id    = request.GET.get('semester', '').strip()
    semesters = Semester.objects.annotate(
        enrolled_count=Count('enrollments', distinct=True)
    ).order_by('-is_active', '-start_date')

    selected_sem       = None
    enrolled_students  = []
    available_students = []
    enrolled_objs      = []

    if sem_id:
        selected_sem  = get_object_or_404(Semester, pk=sem_id)
        enrolled_objs = (
            StudentEnrollment.objects
            .filter(semester=selected_sem)
            .select_related('student', 'student__userprofile')
            .order_by('student__last_name', 'student__first_name')
        )
        enrolled_ids = [e.student_id for e in enrolled_objs]
        available_students = (
            User.objects.filter(userprofile__user_type='student')
            .exclude(id__in=enrolled_ids)
            .select_related('userprofile')
            .order_by('last_name', 'first_name')
        )

    return render(request, 'admin/manage_enrollments.html', {
        'semesters':         semesters,
        'selected_sem':      selected_sem,
        'enrolled_objs':     enrolled_objs,
        'available_students': available_students,
        'sem_id':            sem_id,
    })


@login_required
def admin_assign_students(request):
    if not _admin_guard(request):
        return redirect('dashboard')

    if request.method != 'POST':
        return redirect('admin_manage_enrollments')

    sem_id      = request.POST.get('semester_id', '').strip()
    student_ids = request.POST.getlist('student_ids')

    if not sem_id:
        messages.error(request, 'No semester selected.')
        return redirect('admin_manage_enrollments')

    sem   = get_object_or_404(Semester, pk=sem_id)
    added = 0
    for sid in student_ids:
        _, created = StudentEnrollment.objects.get_or_create(student_id=sid, semester=sem)
        if created:
            added += 1

    if added:
        messages.success(request, f'{added} student{"s" if added != 1 else ""} enrolled in {sem}.')
    else:
        messages.info(request, 'No new students were added (already enrolled or none selected).')

    return redirect(f"{reverse('admin_manage_enrollments')}?semester={sem_id}")


@login_required
def admin_remove_enrollment(request, enr_id):
    if not _admin_guard(request):
        return redirect('dashboard')

    enr    = get_object_or_404(StudentEnrollment, pk=enr_id)
    sem_id = enr.semester_id

    if request.method == 'POST':
        name = enr.student.get_full_name() or enr.student.username
        enr.delete()
        messages.success(request, f'{name} removed from {enr.semester}.')

    return redirect(f"{reverse('admin_manage_enrollments')}?semester={sem_id}")


# ==================== ADMIN SUBJECT DETAIL ====================

@login_required
def admin_subject_detail(request, sub_id):
    if not _admin_guard(request):
        return redirect('dashboard')

    sub = get_object_or_404(
        Subject.objects.select_related('semester', 'lecturer', 'lecturer__userprofile'),
        pk=sub_id
    )

    # Students enrolled in the same semester
    enrolled_students = (
        StudentEnrollment.objects
        .filter(semester=sub.semester)
        .select_related('student', 'student__userprofile')
        .order_by('student__last_name', 'student__first_name')
    )

    # Replacement request history for this subject
    replacements = (
        ClassReplacementRequest.objects
        .filter(subject=sub)
        .select_related('lecturer', 'venue')
        .order_by('-replacement_date')[:20]
    )

    replacement_counts = ClassReplacementRequest.objects.filter(subject=sub).aggregate(
        total    = Count('id'),
        approved = Count('id', filter=Q(status='approved')),
        pending  = Count('id', filter=Q(status='pending')),
        rejected = Count('id', filter=Q(status='rejected')),
    )

    return render(request, 'admin/subject_detail.html', {
        'sub':                sub,
        'enrolled_students':  enrolled_students,
        'replacements':       replacements,
        'replacement_counts': replacement_counts,
    })


# ==================== ADMIN LECTURER DETAIL ====================

@login_required
def admin_lecturer_detail(request, user_id):
    if not _admin_guard(request):
        return redirect('dashboard')

    lecturer = get_object_or_404(User, pk=user_id)
    profile  = get_object_or_404(UserProfile, user=lecturer, user_type='lecturer')

    # All subjects taught, grouped by semester
    subjects = (
        Subject.objects
        .filter(lecturer=lecturer)
        .select_related('semester')
        .order_by('-semester__start_date', 'subject_code')
    )

    # Build per-semester summary
    sem_map = {}
    total_credit = 0
    total_contact = 0
    for sub in subjects:
        sid = sub.semester_id
        if sid not in sem_map:
            sem_map[sid] = {
                'semester': sub.semester,
                'subjects': [],
                'credit_hours': 0,
                'contact_hours': 0,
            }
        sem_map[sid]['subjects'].append(sub)
        sem_map[sid]['credit_hours']  += sub.credit_hours
        sem_map[sid]['contact_hours'] += sub.total_contact_hours
        total_credit  += sub.credit_hours
        total_contact += sub.total_contact_hours

    semesters_taught = list(sem_map.values())

    # Replacement request history
    replacements = (
        ClassReplacementRequest.objects
        .filter(lecturer=lecturer)
        .select_related('subject', 'venue')
        .order_by('-replacement_date')[:15]
    )

    request_counts = ClassReplacementRequest.objects.filter(lecturer=lecturer).aggregate(
        total    = Count('id'),
        approved = Count('id', filter=Q(status='approved')),
        pending  = Count('id', filter=Q(status='pending')),
        rejected = Count('id', filter=Q(status='rejected')),
    )

    return render(request, 'admin/lecturer_detail.html', {
        'lecturer':         lecturer,
        'profile':          profile,
        'semesters_taught': semesters_taught,
        'total_credit':     total_credit,
        'total_contact':    total_contact,
        'total_subjects':   subjects.count(),
        'replacements':     replacements,
        'request_counts':   request_counts,
    })