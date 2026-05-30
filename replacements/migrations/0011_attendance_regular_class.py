from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('replacements', '0010_venue_type_block'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # 1. Add session_type with default so existing rows get 'replacement'
        migrations.AddField(
            model_name='attendancesession',
            name='session_type',
            field=models.CharField(
                choices=[('replacement', 'Replacement Class'), ('regular', 'Regular Class')],
                default='replacement',
                max_length=20,
            ),
        ),
        # 2. Add schedule FK (nullable)
        migrations.AddField(
            model_name='attendancesession',
            name='schedule',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='attendance_sessions',
                to='replacements.classschedule',
            ),
        ),
        # 3. Add class_date
        migrations.AddField(
            model_name='attendancesession',
            name='class_date',
            field=models.DateField(blank=True, null=True),
        ),
        # 4. Add opened_by
        migrations.AddField(
            model_name='attendancesession',
            name='opened_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='opened_attendance_sessions',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        # 5. Change replacement_request from OneToOneField → nullable ForeignKey
        migrations.AlterField(
            model_name='attendancesession',
            name='replacement_request',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='attendance_sessions',
                to='replacements.classreplacementrequest',
            ),
        ),
        # 6. Add unique constraint for regular sessions
        migrations.AddConstraint(
            model_name='attendancesession',
            constraint=models.UniqueConstraint(
                condition=models.Q(session_type='regular'),
                fields=['schedule', 'class_date'],
                name='unique_regular_session_per_day',
            ),
        ),
    ]
