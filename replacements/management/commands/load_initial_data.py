"""
Management command: load_initial_data
Runs automatically during Railway startup (see Procfile).
Loads fixtures/initial_data.json only when the database is empty.
Safe to run on every deploy — skips if data already exists.
"""
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = 'Load fixture data on first deploy (skips if data already exists)'

    def handle(self, *args, **options):
        if User.objects.exists():
            self.stdout.write('Data already loaded — skipping fixture import.')
            return

        self.stdout.write('First deploy detected — loading initial fixture data...')
        try:
            call_command('loaddata', 'fixtures/initial_data.json', verbosity=0)
            count = User.objects.count()
            self.stdout.write(
                self.style.SUCCESS(f'Fixture loaded successfully. {count} users in database.')
            )
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Fixture load failed: {e}'))
            raise
