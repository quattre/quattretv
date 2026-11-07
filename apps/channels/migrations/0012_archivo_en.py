import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('channels', '0011_archivo_de_otro_canal'),
        ('pvr', '0007_ajustes_grabacion'),
    ]

    operations = [
        migrations.AddField(
            model_name='channel',
            name='archivo_en',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='canales_archivados', to='pvr.storageserver', help_text='Grabador nuestro que archiva este canal. Vacio = lo archiva Ministra en storage1.'),
        ),
    ]
