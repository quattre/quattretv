from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('epg', '0002_ultimos_7_dias'),
        ('devices', '0003_device_usa_http_legacy'),
        ('channels', '0008_channel_origen_grabador'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProgresoArchivo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('inicio', models.DateTimeField(help_text='Inicio del programa en la guia')),
                ('posicion', models.PositiveIntegerField(help_text='Segundos desde el inicio')),
                ('duracion', models.PositiveIntegerField()),
                ('actualizado', models.DateTimeField(auto_now=True)),
                ('channel', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to='channels.channel')),
                ('device', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='progresos_archivo', to='devices.device')),
            ],
            options={
                'ordering': ['-actualizado'],
                'unique_together': {('device', 'channel', 'inicio')},
            },
        ),
    ]
