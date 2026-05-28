"""
Generate realistic sample ClassReplacementRequests spread across the last 6 months.

Usage:
    python manage.py seed_requests            # add ~80 new requests
    python manage.py seed_requests --clear    # delete all existing requests first, then seed
    python manage.py seed_requests --count 120
"""

import random
from datetime import date, timedelta, datetime
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from replacements.models import (
    ClassReplacementRequest, Subject, Venue, UserProfile, Notification
)

REASONS = [
    "Attending a national academic conference on computer networks.",
    "Medical appointment that cannot be rescheduled.",
    "Faculty professional development workshop.",
    "Invited as guest speaker at another institution.",
    "Personal emergency requiring immediate attention.",
    "Research collaboration meeting with industry partner.",
    "Attending ministry-level seminar on curriculum development.",
    "Lab equipment maintenance requires class relocation.",
    "Public holiday falls on usual class day; makeup class needed.",
    "Official duty — external examination invigilation.",
    "Postgraduate research supervision commitment.",
    "Attending IEEE workshop on emerging technologies.",
    "Medical certificate — doctor-ordered rest.",
    "Faculty retreat and strategic planning session.",
    "Invited to participate in national skills competition judging.",
    "Annual staff appraisal and HR training day.",
    "University convocation duties as faculty marshal.",
    "Travel for student industrial visit coordination.",
    "Clash with another compulsory faculty meeting.",
    "Lab practical session rescheduled due to equipment delivery.",
]

TIME_SLOTS = [
    "8:00 AM - 10:00 AM",
    "10:00 AM - 12:00 PM",
    "12:00 PM - 2:00 PM",
    "2:00 PM - 4:00 PM",
    "4:00 PM - 6:00 PM",
    "8:00 AM - 11:00 AM",
    "11:00 AM - 1:00 PM",
    "3:00 PM - 5:00 PM",
]


def random_weekday(start: date, end: date) -> date:
    """Return a random weekday (Mon-Fri) between start and end."""
    delta = (end - start).days
    for _ in range(200):
        d = start + timedelta(days=random.randint(0, delta))
        if d.weekday() < 5:   # 0=Mon … 4=Fri
            return d
    return start


class Command(BaseCommand):
    help = 'Seed sample replacement requests for statistics demonstration'

    def add_arguments(self, parser):
        parser.add_argument(
            '--count', type=int, default=80,
            help='Number of requests to create (default: 80)',
        )
        parser.add_argument(
            '--clear', action='store_true',
            help='Delete ALL existing replacement requests before seeding',
        )

    def handle(self, *args, **options):
        count   = options['count']
        do_clear = options['clear']

        if do_clear:
            deleted, _ = ClassReplacementRequest.objects.all().delete()
            self.stdout.write(self.style.WARNING(f'Deleted {deleted} existing requests.'))

        # ── Collect resources ──────────────────────────────────────────────────
        lecturers = list(
            User.objects.filter(userprofile__user_type='lecturer')
                        .select_related('userprofile')
        )
        admins = list(User.objects.filter(userprofile__user_type='admin'))
        subjects = list(Subject.objects.filter(lecturer__isnull=False).select_related('semester'))
        venues   = list(Venue.objects.filter(is_active=True))

        if not lecturers:
            self.stderr.write(self.style.ERROR('No lecturers found. Import data first.'))
            return
        if not subjects:
            self.stderr.write(self.style.ERROR('No subjects with assigned lecturers found.'))
            return
        if not venues:
            self.stderr.write(self.style.ERROR('No active venues found.'))
            return
        if not admins:
            self.stderr.write(self.style.ERROR('No admin users found.'))
            return

        # ── Date range: last 6 months split into bands ────────────────────────
        today = date.today()
        # Build 6 monthly buckets (oldest -> newest)
        bands = []
        for i in range(5, -1, -1):
            m_end   = today.replace(day=1) - timedelta(days=1) if i > 0 else today
            m_start = (today.replace(day=1) - timedelta(days=30 * i)).replace(day=1)
            if m_start > today:
                continue
            if m_end > today:
                m_end = today
            bands.append((m_start, m_end))

        # Distribute count across bands with slight upward trend
        weights = [0.08, 0.10, 0.14, 0.18, 0.22, 0.28]
        if len(bands) < 6:
            weights = weights[-len(bands):]
        total_w = sum(weights[:len(bands)])
        per_band = [max(1, int(count * w / total_w)) for w in weights[:len(bands)]]
        # Fix rounding
        diff = count - sum(per_band)
        per_band[-1] += diff

        # ── Status distribution ────────────────────────────────────────────────
        # ~60% approved, ~15% pending (recent only), ~25% rejected
        # Older months: mostly approved/rejected; recent month: mix with pending

        created = 0
        skipped = 0

        for band_idx, (b_start, b_end) in enumerate(bands):
            is_latest = (band_idx == len(bands) - 1)
            n = per_band[band_idx]

            for _ in range(n):
                lecturer = random.choice(lecturers)
                # Pick a subject assigned to this lecturer if possible
                lec_subjects = [s for s in subjects if s.lecturer_id == lecturer.id]
                if not lec_subjects:
                    lec_subjects = subjects
                subject = random.choice(lec_subjects)
                venue   = random.choice(venues)

                orig_date = random_weekday(b_start, b_end)
                # Replacement 3-14 days after original
                repl_date = random_weekday(
                    orig_date + timedelta(days=3),
                    min(orig_date + timedelta(days=14), today + timedelta(days=30))
                )

                orig_slot = random.choice(TIME_SLOTS)
                repl_slot = random.choice(TIME_SLOTS)
                reason    = random.choice(REASONS)

                # Status weights
                if is_latest:
                    status = random.choices(
                        ['approved', 'pending', 'rejected'],
                        weights=[50, 30, 20]
                    )[0]
                else:
                    status = random.choices(
                        ['approved', 'pending', 'rejected'],
                        weights=[62, 5, 33]
                    )[0]

                approved_by = random.choice(admins) if status in ('approved', 'rejected') else None

                # created_at: random datetime within the band
                band_start_dt = datetime.combine(b_start, datetime.min.time())
                band_end_dt   = datetime.combine(b_end,   datetime.max.time())
                delta_secs    = int((band_end_dt - band_start_dt).total_seconds())
                created_at    = band_start_dt + timedelta(seconds=random.randint(0, delta_secs))
                created_at    = timezone.make_aware(created_at) if timezone.is_naive(created_at) else created_at

                try:
                    req = ClassReplacementRequest(
                        lecturer             = lecturer,
                        subject              = subject,
                        original_date        = orig_date,
                        original_time_slot   = orig_slot,
                        replacement_date     = repl_date,
                        replacement_time_slot= repl_slot,
                        venue                = venue,
                        reason               = reason,
                        status               = status,
                        approved_by          = approved_by,
                    )
                    req.save()
                    # Override auto_now_add created_at via queryset update
                    ClassReplacementRequest.objects.filter(pk=req.pk).update(created_at=created_at)
                    created += 1
                except Exception as e:
                    skipped += 1
                    self.stderr.write(f'  [SKIP] {e}')

        # ── Summary ────────────────────────────────────────────────────────────
        from django.db.models import Count
        totals = {
            r['status']: r['c']
            for r in ClassReplacementRequest.objects.values('status').annotate(c=Count('id'))
        }
        self.stdout.write(self.style.SUCCESS(
            f'\nSeeding complete!\n'
            f'  Created : {created}  |  Skipped: {skipped}\n'
            f'\nDatabase totals now:\n'
            f'  Approved : {totals.get("approved", 0)}\n'
            f'  Pending  : {totals.get("pending",  0)}\n'
            f'  Rejected : {totals.get("rejected", 0)}\n'
            f'  TOTAL    : {sum(totals.values())}'
        ))
