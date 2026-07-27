from django.db import migrations, models
import django.db.models.deletion


def create_players_from_members(apps, schema_editor):
    Player = apps.get_model('teams', 'Player')
    Member = apps.get_model('teams', 'Member')

    players_by_name = {}
    for member in Member.objects.order_by('id'):
        if member.name not in players_by_name:
            players_by_name[member.name] = Player.objects.create(name=member.name)
        member.player = players_by_name[member.name]
        member.save(update_fields=['player'])


def unlink_players(apps, schema_editor):
    Member = apps.get_model('teams', 'Member')
    Member.objects.update(player=None)


class Migration(migrations.Migration):

    dependencies = [
        ('teams', '0006_alter_member_unique_together_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='Player',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(db_index=True, max_length=100)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.AddField(
            model_name='member',
            name='player',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='members',
                to='teams.player',
            ),
        ),
        migrations.RunPython(create_players_from_members, unlink_players),
        migrations.AlterField(
            model_name='member',
            name='player',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='members',
                to='teams.player',
            ),
        ),
    ]
