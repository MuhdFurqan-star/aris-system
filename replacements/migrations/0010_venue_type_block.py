from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('replacements', '0009_add_class_schedule'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # 1. Add venue_type to Venue
        migrations.AddField(
            model_name='venue',
            name='venue_type',
            field=models.CharField(
                choices=[
                    ('classroom', 'Classroom'),
                    ('lab',       'Computer Lab'),
                    ('workshop',  'Workshop'),
                    ('studio',    'Studio'),
                ],
                default='classroom',
                max_length=20,
            ),
        ),

        # 2. Add optional venue FK to ClassSchedule
        migrations.AddField(
            model_name='classschedule',
            name='venue',
            field=models.ForeignKey(
                blank=True,
                help_text='Regular venue for this class (optional — used for venue availability checks)',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='scheduled_classes',
                to='replacements.venue',
            ),
        ),

        # 3. Create VenueBlock model
        migrations.CreateModel(
            name='VenueBlock',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('blocked_date', models.DateField()),
                ('reason', models.CharField(blank=True, max_length=200)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='venue_blocks_created',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('venue', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='blocks',
                    to='replacements.venue',
                )),
            ],
            options={
                'ordering': ['blocked_date'],
                'unique_together': {('venue', 'blocked_date')},
            },
        ),
    ]
