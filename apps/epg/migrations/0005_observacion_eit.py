from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('channels', '0008_channel_origen_grabador'),
        ('epg', '0004_hora_real'),
    ]

    operations = [
        migrations.CreateModel(
            name='ObservacionEit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('inicio', models.DateTimeField(db_index=True)),
                ('nombre', models.CharField(max_length=300)),
                ('visto', models.DateTimeField()),
                ('channel', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to='channels.channel')),
            ],
            options={
                'ordering': ['-inicio'],
                'unique_together': {('channel', 'inicio', 'nombre')},
            },
        ),
    ]
