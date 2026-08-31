from django.db import migrations, models


def esconder_adultos_en_lg(apps, schema_editor):
    """
    Los canales +18 dejan de viajar a los televisores LG.

    LG no admite aplicaciones con contenido para adultos sin un contrato aparte
    con LG Electronics -- lo dice su guia del Seller Lounge, en el apartado de
    clasificacion por edades. Asi que el canal se queda para los MAG y los
    Android, que es donde siempre ha estado, y no se manda a los LG.

    Solo toca los canales marcados como +18. El resto se queda como estaba: sin
    nada en el campo, o sea visible para todos.
    """
    Channel = apps.get_model('channels', 'Channel')
    Channel.objects.filter(is_adult=True).update(oculto_para=',lg,')


def volver_a_mostrarlos(apps, schema_editor):
    Channel = apps.get_model('channels', 'Channel')
    Channel.objects.filter(oculto_para=',lg,').update(oculto_para='')


class Migration(migrations.Migration):

    dependencies = [
        ('channels', '0005_cdnserver_channel_cdn_name_channel_cdn'),
    ]

    operations = [
        migrations.AddField(
            model_name='channel',
            name='oculto_para',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Aparatos que NO veran este canal. Vacio = lo ven todos.',
                max_length=200,
                verbose_name='Oculto para',
            ),
        ),
        migrations.RunPython(esconder_adultos_en_lg, volver_a_mostrarlos),
    ]
