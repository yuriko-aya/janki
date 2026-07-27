# Generated manually

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('teams', '0007_add_player_model'),
    ]

    operations = [
        migrations.AddField(
            model_name='player',
            name='user',
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='player_profile',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
