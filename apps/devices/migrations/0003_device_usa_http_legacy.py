"""
Todo aparato nuevo pide el video por https; el 1500 pasa a ser una excepcion
marcada aparato por aparato.

Los que ya estaban dados de alta cuando esto se aplica llevaban pidiendo el
puerto 1500 y ahi seguian viendo la television, asi que se les marca la
excepcion para no dejarlos en negro de un dia para otro. A partir de aqui,
cualquier aparato que se de de alta entra por https sin que nadie haga nada.

Se desmarcan de uno en uno segun se compruebe que cada deco puede con el https.
"""
from django.db import migrations, models


def marcar_los_que_ya_estaban(apps, schema_editor):
    Device = apps.get_model('devices', 'Device')
    # Solo los decos: una television o un navegador nunca han pedido el 1500,
    # porque un navegador no carga video sin cifrar desde una pagina segura.
    Device.objects.filter(device_type__in=['mag', 'android']).update(usa_http_legacy=True)


def desmarcar(apps, schema_editor):
    Device = apps.get_model('devices', 'Device')
    Device.objects.update(usa_http_legacy=False)


class Migration(migrations.Migration):

    dependencies = [
        ('devices', '0002_device_uid_alter_device_device_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='device',
            name='usa_http_legacy',
            field=models.BooleanField(
                default=False,
                help_text='Solo para decos viejos que no pueden con HTTPS. Un '
                          'aparato nuevo nunca lleva esto marcado: todos entran '
                          'por HTTPS.',
                verbose_name='Pedir el video sin cifrar (aparato antiguo)',
            ),
        ),
        migrations.RunPython(marcar_los_que_ya_estaban, desmarcar),
    ]
