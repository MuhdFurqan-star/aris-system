"""
Management command: load_initial_data
Runs automatically during Railway startup (see Procfile).
Loads fixtures/initial_data.json only when no semesters exist.
After loading, resets all PostgreSQL sequences so new records can be inserted.
"""
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.db import connection


def _reset_sequences():
    """Reset PostgreSQL auto-increment sequences after fixture import."""
    if connection.vendor != 'postgresql':
        return

    tables = [
        # replacements app
        'replacements_venue', 'replacements_semester', 'replacements_subject',
        'replacements_classreplacementrequest', 'replacements_venuefeedback',
        'replacements_venueblock', 'replacements_notification',
        'replacements_attendancesession', 'replacements_attendancerecord',
        'replacements_classschedule', 'replacements_studentenrollment',
        'replacements_replacementbookmark', 'replacements_userprofile',
        # auth
        'auth_user', 'auth_group', 'auth_permission',
    ]

    with connection.cursor() as cursor:
        for table in tables:
            try:
                cursor.execute(f"""
                    SELECT setval(
                        pg_get_serial_sequence('{table}', 'id'),
                        COALESCE(MAX(id), 1),
                        true
                    ) FROM "{table}"
                """)
            except Exception:
                connection.rollback()  # reset transaction on error, keep going


class Command(BaseCommand):
    help = 'Load fixture data on first deploy (skips if semester data already exists)'

    def handle(self, *args, **options):
        from replacements.models import Semester

        if Semester.objects.exists():
            self.stdout.write('Fixture data already present — skipping.')
            _reset_sequences()  # Always ensure sequences are correct
            return

        self.stdout.write('No semester data found — loading initial fixture...')
        try:
            call_command('loaddata', 'fixtures/initial_data.json', verbosity=0)
            from django.contrib.auth.models import User
            self.stdout.write(f'Fixture loaded: {User.objects.count()} users, '
                              f'{Semester.objects.count()} semesters.')
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Fixture load failed: {e}'))
            raise

        self.stdout.write('Resetting PostgreSQL sequences...')
        _reset_sequences()
        self.stdout.write(self.style.SUCCESS('Done — sequences reset. System ready.'))
