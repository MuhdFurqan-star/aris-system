"""
Management command: load_initial_data
Runs automatically during Railway startup (see Procfile).
Loads fixtures/initial_data.json only when no semesters exist.
Checks Semester (not User) so manually-created admin accounts
don't prevent the fixture from loading.
"""
from django.core.management.base import BaseCommand
from django.core.management import call_command


class Command(BaseCommand):
    help = 'Load fixture data on first deploy (skips if semester data already exists)'

    def handle(self, *args, **options):
        from replacements.models import Semester
        if Semester.objects.exists():
            self.stdout.write('Fixture data already present — skipping.')
            return

        self.stdout.write('No semester data found — loading initial fixture...')
        try:
            call_command('loaddata', 'fixtures/initial_data.json', verbosity=0)
            from django.contrib.auth.models import User
            self.stdout.write(self.style.SUCCESS(
                f'Fixture loaded successfully. '
                f'{User.objects.count()} users, '
                f'{Semester.objects.count()} semesters in database.'
            ))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Fixture load failed: {e}'))
            raise
