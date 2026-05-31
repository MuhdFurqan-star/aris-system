"""
Seed APPROVED replacement requests specifically to populate the Admin venue heatmap.

The heatmap (views.admin_venue_heatmap) counts ONLY approved ClassReplacementRequest
rows, grouped by  venue × weekday(Mon-Fri) × replacement_time_slot, where the slot
string MUST match the heatmap's TIME_SLOTS format e.g. "08:00-09:00".

This command:
  * uses your EXISTING active venues, subjects (with a lecturer), lecturers and admin,
  * gives EVERY active venue some usage (no empty venue),
  * but weights venues / slots / days so SOME cells are clearly hotter than others.

Usage:
    python manage.py seed_heatmap_demo                 # default intensity
    python manage.py seed_heatmap_demo --scale 7       # darker / busier heatmap
    python manage.py seed_heatmap_demo --clear         # remove only THIS command's demo rows, then reseed
"""

import random
from datetime import date, timedelta, datetime
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from replacements.models import ClassReplacementRequest, Subject, Venue

# Must match TIME_SLOTS in views.admin_venue_heatmap EXACTLY.
TIME_SLOTS = [
    '08:00-09:00', '09:00-10:00', '10:00-11:00', '11:00-12:00',
    '12:00-13:00', '13:00-14:00', '14:00-15:00', '15:00-16:00',
    '16:00-17:00', '17:00-18:00',
]

# Relative popularity of each slot (peak mid-morning + mid-afternoon, lunch dip).
SLOT_WEIGHTS = [0.4, 0.8, 1.0, 0.9, 0.3, 0.5, 0.9, 1.0, 0.7, 0.4]

# Relative popularity per weekday (0=Mon … 4=Fri).
DAY_WEIGHTS = [1.0, 0.9, 1.0, 0.8, 0.5]

# Tiered venue popularity — cycled across venues so some venues run hot, some cool,
# but every venue gets a non-zero weight.
VENUE_TIERS = [1.0, 0.85, 0.7, 0.55, 0.4]

# Tag so the rows are identifiable / removable.
DEMO_TAG = '[DEMO-HEATMAP]'

REASONS = [
    "Makeup class after public holiday.",
    "Lecturer attending faculty workshop.",
    "Lab maintenance required class relocation.",
    "Guest lecture rescheduled to this slot.",
    "Medical appointment — class moved.",
    "Clash with faculty meeting resolved by replacement.",
    "Industrial visit coordination.",
    "Curriculum review session.",
]


class Command(BaseCommand):
    help = 'Seed approved replacement requests to populate the venue heatmap for demo.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--scale', type=float, default=5.0,
            help='Intensity multiplier. Higher = busier/darker heatmap (default: 5.0).',
        )
        parser.add_argument(
            '--clear', action='store_true',
            help='Delete previously seeded heatmap-demo rows before seeding again.',
        )
        parser.add_argument(
            '--skip-if-seeded', action='store_true',
            help='Do nothing if heatmap-demo rows already exist (safe for deploy hooks).',
        )

    def handle(self, *args, **options):
        scale = options['scale']

        existing = ClassReplacementRequest.objects.filter(reason__startswith=DEMO_TAG)

        # Idempotent mode for deploy hooks: bail out if already seeded.
        if options['skip_if_seeded'] and not options['clear'] and existing.exists():
            self.stdout.write(self.style.SUCCESS(
                f'Heatmap demo already seeded ({existing.count()} rows). Skipping.'
            ))
            return

        if options['clear']:
            deleted, _ = existing.delete()
            self.stdout.write(self.style.WARNING(
                f'Cleared {deleted} previously seeded heatmap-demo rows.'
            ))

        # ── Gather existing resources ──────────────────────────────────────────
        venues = list(Venue.objects.filter(is_active=True).order_by('id'))
        subjects = list(
            Subject.objects.filter(lecturer__isnull=False).select_related('lecturer')
        )
        admins = list(User.objects.filter(userprofile__user_type='admin'))

        if not venues:
            self.stderr.write(self.style.ERROR('No active venues. Add venues first.'))
            return
        if not subjects:
            self.stderr.write(self.style.ERROR(
                'No subjects with an assigned lecturer. Assign lecturers to subjects first.'
            ))
            return
        if not admins:
            self.stderr.write(self.style.ERROR('No admin user found to approve requests.'))
            return

        admin = admins[0]

        # Spread replacement dates across the last 8 weeks (weekday is what matters).
        today = date.today()
        # Most recent Monday on/before today.
        base_monday = today - timedelta(days=today.weekday())

        def a_date_for_weekday(day_idx):
            """Return a real date on the given weekday, within the last ~8 weeks."""
            weeks_back = random.randint(0, 7)
            return base_monday - timedelta(weeks=weeks_back) + timedelta(days=day_idx)

        created = 0
        venue_totals = {}

        for v_idx, venue in enumerate(venues):
            venue_weight = VENUE_TIERS[v_idx % len(VENUE_TIERS)]
            venue_total_here = 0

            for day_idx in range(5):                       # Mon-Fri
                for slot_idx, slot in enumerate(TIME_SLOTS):
                    expected = (
                        venue_weight
                        * SLOT_WEIGHTS[slot_idx]
                        * DAY_WEIGHTS[day_idx]
                        * scale
                        * random.uniform(0.5, 1.15)
                    )
                    count = int(round(expected))
                    # Keep the heatmap organic: low-weight cells often land on 0.
                    if count <= 0:
                        continue

                    for _ in range(count):
                        subject = random.choice(subjects)
                        lecturer = subject.lecturer
                        repl_date = a_date_for_weekday(day_idx)
                        orig_date = repl_date - timedelta(days=random.randint(3, 10))
                        orig_slot = random.choice(TIME_SLOTS)

                        req = ClassReplacementRequest(
                            lecturer=lecturer,
                            subject=subject,
                            original_date=orig_date,
                            original_time_slot=orig_slot,
                            replacement_date=repl_date,
                            replacement_time_slot=slot,   # heatmap-format slot
                            venue=venue,
                            reason=f'{DEMO_TAG} {random.choice(REASONS)}',
                            status='approved',
                            approved_by=admin,
                        )
                        req.save()
                        created += 1
                        venue_total_here += 1

            # Guarantee EVERY venue appears on the heatmap with at least a little usage.
            if venue_total_here == 0:
                hot_slot = TIME_SLOTS[SLOT_WEIGHTS.index(max(SLOT_WEIGHTS))]
                for _ in range(2):
                    subject = random.choice(subjects)
                    repl_date = a_date_for_weekday(0)       # Monday
                    ClassReplacementRequest.objects.create(
                        lecturer=subject.lecturer,
                        subject=subject,
                        original_date=repl_date - timedelta(days=7),
                        original_time_slot=hot_slot,
                        replacement_date=repl_date,
                        replacement_time_slot=hot_slot,
                        venue=venue,
                        reason=f'{DEMO_TAG} Baseline usage.',
                        status='approved',
                        approved_by=admin,
                    )
                    created += 1
                    venue_total_here += 1

            venue_totals[venue.venue_name] = venue_total_here

        # ── Summary ────────────────────────────────────────────────────────────
        self.stdout.write(self.style.SUCCESS(
            f'\nHeatmap demo seeding complete! Created {created} approved requests '
            f'across {len(venues)} venues.\n'
        ))
        self.stdout.write('Per-venue usage (higher = darker on heatmap):')
        peak = max(venue_totals.values()) if venue_totals else 1
        for name, total in sorted(venue_totals.items(), key=lambda x: -x[1]):
            bar = '#' * max(1, int((total / peak) * 40))
            self.stdout.write(f'  {name[:24]:<24} {total:>4}  {bar}')
        self.stdout.write(self.style.SUCCESS(
            '\nOpen the Admin -> Venue Heatmap page to see the result.'
        ))
