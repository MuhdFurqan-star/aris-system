from django.db import models
from django.contrib.auth.models import User

class UserProfile(models.Model):
    USER_TYPES = (
        ('student', 'Student'),
        ('lecturer', 'Lecturer'),
        ('admin', 'Admin'),
    )
    COURSE_CHOICES = (
        ('CS',  'Computer Science'),
        ('LH',  'Landscape & Horticulture'),
        ('ACC', 'Accounting'),
        ('BS',  'Business Study'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    user_type = models.CharField(max_length=10, choices=USER_TYPES)
    employee_id = models.CharField(max_length=50, null=True, blank=True)
    student_id = models.CharField(max_length=50, null=True, blank=True)
    course = models.CharField(
        max_length=10, choices=COURSE_CHOICES,
        null=True, blank=True,
        help_text='Course / department this user belongs to.',
    )

    def __str__(self):
        return f"{self.user.username} - {self.user_type}"

class Semester(models.Model):
    COURSE_CHOICES = (
        ('CS',  'Computer Science'),
        ('LH',  'Landscape & Horticulture'),
        ('ACC', 'Accounting'),
        ('BS',  'Business Study'),
    )
    name = models.CharField(max_length=100)
    class_name = models.CharField(max_length=50)
    course = models.CharField(
        max_length=10, choices=COURSE_CHOICES,
        default='CS',
        help_text='Course / programme this semester belongs to.',
    )
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ['name', 'class_name', 'course']

    def __str__(self):
        return f"{self.get_course_display()} — Sem {self.name} Class {self.class_name}"

class Subject(models.Model):
    semester    = models.ForeignKey('Semester', on_delete=models.CASCADE)
    subject_code = models.CharField(max_length=50)
    subject_name = models.CharField(max_length=200)
    description  = models.TextField(blank=True, default='', help_text='Short syllabus or subject description.')
    lecturer     = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    # ── Academic Hours ─────────────────────────────────────────────────────────
    credit_hours            = models.PositiveSmallIntegerField(default=3, help_text='Credit hours awarded to students.')
    lecture_hours_per_week  = models.PositiveSmallIntegerField(default=3, help_text='Lecture contact hours per week.')
    tutorial_hours_per_week = models.PositiveSmallIntegerField(default=0, help_text='Tutorial / discussion hours per week.')
    lab_hours_per_week      = models.PositiveSmallIntegerField(default=0, help_text='Lab / practical hours per week.')
    total_weeks             = models.PositiveSmallIntegerField(default=14, help_text='Number of teaching weeks in the semester.')

    class Meta:
        verbose_name_plural = "Subjects"

    def __str__(self):
        return f"{self.subject_code} - {self.subject_name}"

    @property
    def contact_hours_per_week(self):
        return self.lecture_hours_per_week + self.tutorial_hours_per_week + self.lab_hours_per_week

    @property
    def total_contact_hours(self):
        return self.contact_hours_per_week * self.total_weeks

    @property
    def total_lecture_hours(self):
        return self.lecture_hours_per_week * self.total_weeks

    @property
    def total_tutorial_hours(self):
        return self.tutorial_hours_per_week * self.total_weeks

    @property
    def total_lab_hours(self):
        return self.lab_hours_per_week * self.total_weeks

class Venue(models.Model):

    VENUE_TYPE_CHOICES = [
        ('classroom', 'Classroom'),
        ('lab',       'Computer Lab'),
        ('workshop',  'Workshop'),
        ('studio',    'Studio'),
    ]

    venue_name = models.CharField(max_length=100)
    venue_type = models.CharField(max_length=20, choices=VENUE_TYPE_CHOICES, default='classroom')
    capacity   = models.IntegerField()
    location   = models.CharField(max_length=200)
    facilities = models.TextField(blank=True)
    is_active  = models.BooleanField(default=True)
    picture    = models.ImageField(upload_to='venue_images/', null=True, blank=True)

    def __str__(self):
        return self.venue_name

    class Meta:
        ordering = ['id']

class ClassReplacementRequest(models.Model):
    lecturer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='replacement_requests')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)  
    original_date = models.DateField()
    original_time_slot = models.CharField(max_length=50)
    replacement_date = models.DateField()
    replacement_time_slot = models.CharField(max_length=50)
    venue = models.ForeignKey('Venue', on_delete=models.CASCADE)
    reason = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected')
        ],
        default='pending'
    )
    approved_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='approved_requests'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.subject} - {self.replacement_date}"
    
class VenueFeedback(models.Model):
    ISSUE_STATUS_CHOICES = [
        ('moderate', 'Moderate Issue'),
        ('critical', 'Critical Issue'),
        ('solved', 'Solved'),
    ]

    lecturer = models.ForeignKey(User, on_delete=models.CASCADE)
    venue = models.ForeignKey(Venue, on_delete=models.CASCADE)
    replacement_request = models.ForeignKey(ClassReplacementRequest, on_delete=models.CASCADE, null=True, blank=True)
    feedback_text = models.TextField()
    issue_status = models.CharField(
        max_length=20,
        choices=ISSUE_STATUS_CHOICES,
        default='moderate'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    # Resolution tracking
    is_resolved      = models.BooleanField(default=False)
    resolved_by      = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='resolved_feedbacks'
    )
    resolved_at      = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.venue} - {self.lecturer} - {self.get_issue_status_display()}"

    class Meta:
        verbose_name = 'Venue Feedback'
        verbose_name_plural = 'Venue Feedbacks'
        ordering = ['-created_at']


class VenueBlock(models.Model):
    """Admin can block a venue on a specific date (maintenance, event, etc.)."""
    venue        = models.ForeignKey(Venue, on_delete=models.CASCADE, related_name='blocks')
    blocked_date = models.DateField()
    reason       = models.CharField(max_length=200, blank=True)
    created_by   = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='venue_blocks_created'
    )
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['venue', 'blocked_date']
        ordering = ['blocked_date']

    def __str__(self):
        return f"{self.venue.venue_name} blocked on {self.blocked_date}"

        
class Notification(models.Model):
    NOTIF_TYPES = [
        ('request_submitted',  'Request Submitted'),
        ('request_approved',   'Request Approved'),
        ('request_rejected',   'Request Rejected'),
        ('new_replacement',    'New Replacement Available'),
        ('feedback_submitted', 'Feedback Submitted'),
        ('issue_resolved',     'Issue Resolved'),
    ]
    recipient    = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notif_type   = models.CharField(max_length=30, choices=NOTIF_TYPES)
    title        = models.CharField(max_length=200)
    message      = models.TextField()
    is_read      = models.BooleanField(default=False)
    related_request = models.ForeignKey(
        'ClassReplacementRequest', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='notifications'
    )
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.recipient.username} — {self.title}"


class AttendanceSession(models.Model):
    SESSION_TYPES = [
        ('replacement', 'Replacement Class'),
        ('regular',     'Regular Class'),
    ]
    session_type        = models.CharField(max_length=20, choices=SESSION_TYPES, default='replacement')
    # Replacement class session (existing)
    replacement_request = models.ForeignKey(
        'ClassReplacementRequest', on_delete=models.CASCADE,
        null=True, blank=True, related_name='attendance_sessions'
    )
    # Regular class session (new)
    schedule   = models.ForeignKey(
        'ClassSchedule', on_delete=models.CASCADE,
        null=True, blank=True, related_name='attendance_sessions'
    )
    class_date  = models.DateField(null=True, blank=True)  # actual date for regular sessions
    opened_by   = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='opened_attendance_sessions'
    )
    qr_token    = models.CharField(max_length=64, unique=True)
    is_active   = models.BooleanField(default=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    expires_at  = models.DateTimeField()

    class Meta:
        # Prevent duplicate sessions for the same regular class on the same day
        constraints = [
            models.UniqueConstraint(
                fields=['schedule', 'class_date'],
                condition=models.Q(session_type='regular'),
                name='unique_regular_session_per_day'
            )
        ]

    @property
    def subject(self):
        if self.session_type == 'replacement' and self.replacement_request:
            return self.replacement_request.subject
        if self.session_type == 'regular' and self.schedule:
            return self.schedule.subject
        return None

    @property
    def display_date(self):
        if self.session_type == 'replacement' and self.replacement_request:
            return self.replacement_request.replacement_date
        return self.class_date

    @property
    def display_time(self):
        if self.session_type == 'replacement' and self.replacement_request:
            return self.replacement_request.replacement_time_slot
        if self.session_type == 'regular' and self.schedule:
            return f"{self.schedule.start_time.strftime('%H:%M')}–{self.schedule.end_time.strftime('%H:%M')}"
        return '—'

    @property
    def display_venue(self):
        if self.session_type == 'replacement' and self.replacement_request:
            return self.replacement_request.venue.venue_name
        if self.session_type == 'regular' and self.schedule and self.schedule.venue:
            return self.schedule.venue.venue_name
        return '—'

    @property
    def lecturer(self):
        if self.opened_by:
            return self.opened_by
        if self.session_type == 'replacement' and self.replacement_request:
            return self.replacement_request.lecturer
        if self.session_type == 'regular' and self.schedule:
            return self.schedule.subject.lecturer
        return None

    def __str__(self):
        if self.session_type == 'regular':
            return f"QR Session — {self.schedule} on {self.class_date}"
        return f"QR Session — {self.replacement_request}"


class AttendanceRecord(models.Model):
    session    = models.ForeignKey(AttendanceSession, on_delete=models.CASCADE, related_name='records')
    student    = models.ForeignKey(User, on_delete=models.CASCADE, related_name='attendance_records')
    scanned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['session', 'student']

    def __str__(self):
        return f"{self.student.username} @ {self.session}"


class ClassSchedule(models.Model):
    """Regular weekly class schedule for a subject (fixed recurring slot)."""
    DAY_CHOICES = [
        (0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'),
        (3, 'Thursday'), (4, 'Friday'),
    ]
    subject     = models.ForeignKey('Subject', on_delete=models.CASCADE, related_name='schedules')
    day_of_week = models.IntegerField(choices=DAY_CHOICES)
    start_time  = models.TimeField(help_text='e.g. 08:00')
    end_time    = models.TimeField(help_text='e.g. 10:00')
    venue       = models.ForeignKey(
        'Venue', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='scheduled_classes',
        help_text='Regular venue for this class (optional — used for venue availability checks)',
    )

    class Meta:
        ordering = ['day_of_week', 'start_time']

    def __str__(self):
        return (
            f"{self.subject.subject_code} — "
            f"{self.get_day_of_week_display()} "
            f"{self.start_time:%H:%M}–{self.end_time:%H:%M}"
        )

    @property
    def duration_hours(self):
        return self.end_time.hour - self.start_time.hour


class StudentEnrollment(models.Model):
    """Links a student to a semester/class."""
    student  = models.ForeignKey(User, on_delete=models.CASCADE, related_name='enrollments')
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE, related_name='enrollments')
    enrolled_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['student', 'semester']
        ordering = ['semester', 'student__last_name', 'student__first_name']

    def __str__(self):
        return f"{self.student.get_full_name()} — {self.semester}"


class ReplacementBookmark(models.Model):
    """Students can bookmark replacement classes they're interested in"""
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookmarks')
    replacement = models.ForeignKey(ClassReplacementRequest, on_delete=models.CASCADE, related_name='bookmarked_by')
    bookmarked_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, null=True)  
    
    class Meta:
        unique_together = ['student', 'replacement']
        verbose_name_plural = "Replacement Bookmarks"
    
    def __str__(self):
        return f"{self.student.username} - {self.replacement.subject.subject_code}"