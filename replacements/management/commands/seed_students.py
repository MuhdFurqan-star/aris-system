"""
Seed dummy students (20 per class group, Semesters 1-5) using Malaysian names
and assign realistic weekly class schedules based on the DCS programme structure.

Usage:
    python manage.py seed_students            # create students + schedules
    python manage.py seed_students --clear    # wipe dummy data first, then seed
    python manage.py seed_students --schedules-only  # only (re)seed schedules
"""

import random
from datetime import time
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from replacements.models import (
    UserProfile, Semester, Subject, StudentEnrollment, ClassSchedule
)

# ---------------------------------------------------------------------------
# Malaysian name pools
# ---------------------------------------------------------------------------
MALE_FIRST = [
    'Ahmad', 'Muhammad', 'Mohd', 'Amir', 'Hafiz', 'Syafiq', 'Razif',
    'Luqman', 'Izzat', 'Farhan', 'Nazrin', 'Taufiq', 'Haikal', 'Irfan',
    'Faizal', 'Haziq', 'Fikri', 'Akmal', 'Redzwan', 'Atiq', 'Iman',
    'Nazran', 'Adam', 'Arif', 'Zulhilmi', 'Daniel', 'Azfarul', 'Ridhwan',
    'Faris', 'Hakim', 'Asyraf', 'Ikhwan', 'Zarif', 'Nabil', 'Huzaifah',
]
MALE_MIDDLE = [
    'Syahril', 'Zulkifli', 'Hakimi', 'Azri', 'Firdaus', 'Khairul',
    'Shafiq', 'Asyraf', 'Zikri', 'Hazwan', 'Thaqif', 'Mukhriz',
    'Harith', 'Ammar', 'Zulaikha', 'Akiff', 'Safwan', 'Fitri',
]
MALE_BIN = [
    'Abdullah', 'Ahmad', 'Ali', 'Hassan', 'Ibrahim', 'Ismail',
    'Kamarudin', 'Mansor', 'Nasir', 'Omar', 'Rahman', 'Razak',
    'Salleh', 'Talib', 'Zainudin', 'Bakar', 'Halim', 'Johari',
    'Saari', 'Hamid', 'Yusof', 'Zakaria', 'Latif', 'Wahab', 'Pauzi',
    'Ruslan', 'Azman', 'Lokman', 'Azmi', 'Hussin', 'Ghazali',
]

FEMALE_FIRST = [
    'Nur', 'Nurul', 'Siti', 'Fatin', 'Ainul', 'Nabilah', 'Liyana',
    'Maisarah', 'Raihana', 'Syahirah', 'Izzati', 'Huda', 'Aisyah',
    'Sofea', 'Alya', 'Auni', 'Masyitah', 'Syakirah', 'Azeyrah',
    'Aminah', 'Hannanie', 'Farhana', 'Azyan', 'Suriana', 'Zuyyin',
    'Aina', 'Afini', 'Afiqah', 'Hafeeza', 'Nadia', 'Nabilah',
    'Hasnah', 'Fasihah', 'Batrisyia', 'Alieya',
]
FEMALE_MIDDLE = [
    'Syahirah', 'Izzatul', 'Nadhirah', 'Farhana', 'Zulaikha', 'Amirah',
    'Husna', 'Sofiyah', 'Kamilia', 'Diyana', 'Natasya', 'Khairina',
    'Amanina', 'Safiyah', 'Insyirah',
]
FEMALE_BINTI = MALE_BIN  # binti uses same surname pool

INTAKE_CODES = {
    '1': 'BCS2501',
    '2': 'BCS2402',
    '3': 'BCS2401',
    '4': 'BCS2302',
    '5': 'BCS2301',
}

# ---------------------------------------------------------------------------
# DCS programme schedule template
# (subject_code_fragment, [(day_of_week, start_hour, end_hour), ...])
# Base = Class A.  B adds +2h to start/end.  C shifts day+1.  D shifts day+1 +2h.
# ---------------------------------------------------------------------------
BASE_SCHEDULES = {
    '1': [
        ('CSC 1163', [(0, 8, 10),  (2, 8, 11)]),    # Mon 2h + Wed 3h = 5h
        ('CSC 1373', [(0, 11, 13), (3, 8, 11)]),    # Mon 2h + Thu 3h = 5h
        ('CSC 1293', [(1, 8, 11),  (3, 11, 13)]),   # Tue 3h + Thu 2h = 5h
        ('CSC 1313', [(2, 11, 14), (4, 8, 10)]),    # Wed 3h + Fri 2h = 5h
        ('ISL 1062', [(4, 10, 13)]),                # Fri 3h
        ('SOC 1062', [(4, 10, 13)]),                # Fri 3h (alternative)
        ('KQB/KQK', [(4, 13, 15)]),                 # Fri 2h
        ('KQS/KQU', [(4, 13, 15)]),                 # Fri 2h (alternative)
    ],
    '2': [
        ('CSC 2723', [(0, 8, 11),  (2, 11, 13)]),   # Mon 3h + Wed 2h = 5h
        ('MAT 1103', [(1, 8, 10),  (3, 8, 10)]),    # Tue 2h + Thu 2h = 4h
        ('CSC 2734', [(2, 8, 11),  (4, 8, 11)]),    # Wed 3h + Fri 3h = 6h
        ('ITE 1113', [(1, 11, 14), (3, 11, 13)]),   # Tue 3h + Thu 2h = 5h
        ('KQB/KQK', [(0, 13, 15)]),                 # Mon 2h
        ('KQS/KQU', [(0, 13, 15)]),                 # Mon 2h (alternative)
    ],
    '3': [
        ('CSC 1363', [(0, 8, 11),  (2, 8, 10)]),    # Mon 3h + Wed 2h = 5h
        ('CSC 1093', [(1, 8, 10),  (3, 8, 10)]),    # Discrete Math — Tue+Thu 2h = 4h
        ('MAT 1093', [(1, 8, 10),  (3, 8, 10)]),    # same slot alternate code
        ('CSC 1333', [(2, 11, 14), (4, 8, 10)]),    # Wed 3h + Fri 2h = 5h
        ('CSC 1264', [(0, 13, 16), (3, 13, 16)]),   # Mon 3h + Thu 3h = 6h
        ('ENG 1562', [(4, 11, 14)]),                # Fri 3h
    ],
    '4': [
        ('CSC 1273', [(0, 8, 11),  (2, 8, 10)]),    # Mon 3h + Wed 2h = 5h
        ('QMT 2523', [(1, 8, 11)]),                 # Tue 3h
        ('CSC 2744', [(0, 13, 16), (2, 13, 16)]),   # Mon 3h + Wed 3h = 6h
        ('CSC 2713', [(1, 11, 14), (3, 8, 10)]),    # Tue 3h + Thu 2h = 5h
        ('MPU 2372', [(4, 8, 11)]),                 # Fri 3h
    ],
    '5': [
        ('CSC 2773', [(0, 8, 11),  (2, 8, 10)]),    # Mon 3h + Wed 2h = 5h
        ('CSC 2813', [(0, 11, 14), (2, 11, 13)]),   # Mon 3h + Wed 2h = 5h
        ('CSC 2823', [(1, 8, 11),  (3, 8, 10)]),    # Tue 3h + Thu 2h = 5h
        ('MPU 2232', [(3, 11, 14)]),                # Thu 3h
        ('MPU 2162', [(4, 8, 11)]),                 # Fri 3h
    ],
    '6': [
        ('CSC 2764', [(0, 8, 11),  (3, 8, 11)]),    # Mon 3h + Thu 3h = 6h
        ('CSC 2703', [(1, 8, 11),  (3, 11, 13)]),   # Tue 3h + Thu 2h = 5h
        ('CSC 1283', [(2, 8, 11),  (4, 8, 10)]),    # Wed 3h + Fri 2h = 5h
        ('MPU 2482', [(4, 10, 12)]),                # Fri 2h
    ],
}

# Offsets per class group letter: (day_shift, time_shift_hours)
GROUP_OFFSETS = {
    'A': (0, 0),
    'B': (0, 2),
    'C': (1, 0),
    'D': (1, 2),
}


def _apply_offset(day, start_h, end_h, day_shift, time_shift):
    new_day   = (day + day_shift) % 5
    new_start = min(start_h + time_shift, 16)   # cap so classes end by 18:00
    new_end   = new_start + (end_h - start_h)   # preserve duration
    return new_day, new_start, new_end


def make_name(gender):
    if gender == 'M':
        first  = random.choice(MALE_FIRST)
        middle = random.choice(MALE_MIDDLE)
        family = random.choice(MALE_BIN)
        return f"{first} {middle} bin {family}", first, middle + ' bin ' + family
    else:
        first  = random.choice(FEMALE_FIRST)
        middle = random.choice(FEMALE_MIDDLE)
        family = random.choice(FEMALE_BINTI)
        return f"{first} {middle} binti {family}", first, middle + ' binti ' + family


def make_email(sid):
    return f"{sid.lower().replace('/', '-')}@student.kpm.edu.my"


class Command(BaseCommand):
    help = 'Seed 20 dummy students per class group (Sem 1-5) + class schedules'

    def add_arguments(self, parser):
        parser.add_argument('--clear', action='store_true',
                            help='Delete all dummy students (BCS25xx/BCS24xx/BCS23xx) and schedules first')
        parser.add_argument('--schedules-only', action='store_true',
                            help='Only seed/refresh class schedules (no new students)')
        parser.add_argument('--students-only', action='store_true',
                            help='Only seed students (skip schedule generation)')

    def handle(self, *args, **options):
        do_clear    = options['clear']
        sched_only  = options['schedules_only']
        stud_only   = options['students_only']

        if do_clear:
            self._clear_dummy_data()

        if not sched_only:
            self._seed_students()

        if not stud_only:
            self._seed_schedules()

        self.stdout.write(self.style.SUCCESS('Done!'))

    # -----------------------------------------------------------------------

    def _clear_dummy_data(self):
        patterns = ['BCS2501', 'BCS2402', 'BCS2401', 'BCS2302', 'BCS2301']
        deleted = 0
        for p in patterns:
            qs = UserProfile.objects.filter(student_id__startswith=p)
            users = [up.user for up in qs]
            for u in users:
                u.delete()
                deleted += 1
        self.stdout.write(self.style.WARNING(f'Deleted {deleted} dummy students.'))

        n, _ = ClassSchedule.objects.all().delete()
        self.stdout.write(self.style.WARNING(f'Deleted {n} class schedule entries.'))

    # -----------------------------------------------------------------------

    def _seed_students(self):
        created = skipped = 0

        for sem_name, intake_code in INTAKE_CODES.items():
            sems = Semester.objects.filter(name=sem_name, course='CS').order_by('class_name')
            if not sems.exists():
                self.stdout.write(f'  No semesters found for Sem {sem_name}, skipping.')
                continue

            for sem in sems:
                group_letter = sem.class_name[-1]  # last char: A/B/C/D
                subjects = list(Subject.objects.filter(semester=sem))

                for i in range(1, 21):  # 20 students per class
                    sid = f"{intake_code}-{sem.class_name}{i:02d}"

                    if UserProfile.objects.filter(student_id=sid).exists():
                        skipped += 1
                        continue

                    gender = random.choice(['M', 'F'])
                    full_name, first_name, last_name = make_name(gender)
                    email = make_email(sid)

                    # Ensure unique username
                    uname = sid
                    counter = 1
                    while User.objects.filter(username=uname).exists():
                        uname = f"{sid}-{counter}"
                        counter += 1

                    # Ensure unique email
                    base_email, domain = email.split('@')
                    ec = 1
                    while User.objects.filter(email=email).exists():
                        email = f"{base_email}{ec}@{domain}"
                        ec += 1

                    user = User.objects.create_user(
                        username   = uname,
                        email      = email,
                        first_name = first_name.title(),
                        last_name  = last_name.title(),
                        password   = sid,
                    )
                    UserProfile.objects.create(
                        user       = user,
                        user_type  = 'student',
                        student_id = sid,
                        course     = 'CS',
                    )
                    # Enroll in all subjects of this class group's semester
                    StudentEnrollment.objects.get_or_create(student=user, semester=sem)

                    created += 1

                self.stdout.write(
                    f'  Sem {sem_name} Class {sem.class_name}: '
                    f'20 student slots processed (IDs {intake_code}-{sem.class_name}01–20)'
                )

        self.stdout.write(self.style.SUCCESS(
            f'\nStudents: {created} created, {skipped} already existed.'
        ))

    # -----------------------------------------------------------------------

    def _seed_schedules(self):
        ClassSchedule.objects.all().delete()
        created = 0

        for sem_name, subject_sessions in BASE_SCHEDULES.items():
            sems = Semester.objects.filter(name=sem_name, course='CS').order_by('class_name')
            for sem in sems:
                group_letter = sem.class_name[-1]   # A/B/C/D
                day_shift, time_shift = GROUP_OFFSETS.get(group_letter, (0, 0))

                subjects = Subject.objects.filter(semester=sem)

                for code_frag, sessions in subject_sessions:
                    # Match subjects whose code starts with code_frag
                    matching = subjects.filter(subject_code__startswith=code_frag)
                    if not matching.exists():
                        continue
                    sub = matching.first()

                    for (day, s_h, e_h) in sessions:
                        adj_day, adj_s, adj_e = _apply_offset(
                            day, s_h, e_h, day_shift, time_shift
                        )
                        ClassSchedule.objects.create(
                            subject     = sub,
                            day_of_week = adj_day,
                            start_time  = time(adj_s, 0),
                            end_time    = time(adj_e, 0),
                        )
                        created += 1

        self.stdout.write(self.style.SUCCESS(
            f'Class schedules: {created} entries created.'
        ))
