from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('taikai', '0004_recalculate_member_stats'),
    ]

    operations = [
        migrations.RunPython(migrations.RunPython.noop, migrations.RunPython.noop),
    ]
