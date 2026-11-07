from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('channels', '0010_desfase_archivo_texto'),
    ]

    operations = [
        migrations.AddField(
            model_name='channel',
            name='archivo_desde',
            field=models.DateTimeField(blank=True, null=True, help_text='Lo anterior en el archivo de este canal es de otro canal. Vacio = todo es suyo.'),
        ),
        migrations.AddField(
            model_name='channel',
            name='archivo_anterior',
            field=models.IntegerField(blank=True, null=True, help_text='Carpeta del archivo (id) donde esta lo de este canal hasta "archivo anterior hasta", cuando venia por otra señal.'),
        ),
        migrations.AddField(
            model_name='channel',
            name='archivo_anterior_hasta',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
