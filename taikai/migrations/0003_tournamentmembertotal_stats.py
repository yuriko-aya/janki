from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('taikai', '0002_remove_rank_hanchan_count'),
    ]

    operations = [
        migrations.AddField(
            model_name='tournamentmembertotal',
            name='average_placement',
            field=models.FloatField(default=0.0),
        ),
        migrations.AddField(
            model_name='tournamentmembertotal',
            name='chombo_count',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='tournamentmembertotal',
            name='first_place_count',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='tournamentmembertotal',
            name='fourth_place_count',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='tournamentmembertotal',
            name='second_place_count',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='tournamentmembertotal',
            name='third_place_count',
            field=models.IntegerField(default=0),
        ),
    ]
