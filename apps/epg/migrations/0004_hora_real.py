from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('epg', '0003_seguir_viendo'),
    ]

    operations = [
        migrations.AddField(
            model_name='program',
            name='inicio_real',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='program',
            name='fin_real',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
