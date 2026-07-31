from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('taikai', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='tournament',
            name='rank_hanchan_count',
        ),
        migrations.AlterField(
            model_name='tournament',
            name='fixed_hanchan_count',
            field=models.PositiveIntegerField(
                default=3,
                help_text='Number of fixed hanchans (used in fixed and hybrid modes only)',
            ),
        ),
    ]
