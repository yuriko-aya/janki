from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('taikai', '0005_fix_tournament_totals'),
    ]

    operations = [
        migrations.RunPython(migrations.RunPython.noop, migrations.RunPython.noop),
    ]
