from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('channels', '0002_channel_is_radio'),
    ]

    operations = [
        migrations.AddField(
            model_name='channel',
            name='multicast_url',
            field=models.CharField(
                blank=True,
                help_text='Origen multicast para archivo/grabación, ej. udp://239.0.0.1:1234. '
                          'Es el mismo SRC del EnvironmentFile del CDN; los grabadores '
                          '(dumpstream) leen de aquí, no del HLS.',
                max_length=200,
            ),
        ),
    ]
