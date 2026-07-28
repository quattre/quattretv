"""
Endpoint de salud.

Pensado para mirarlo desde fuera (monitorizacion o un simple curl) y enterarse
de que algo lleva parado antes de que lo cuente un cliente. El caso tipico es
que Celery se caiga y el EPG deje de actualizarse: la web sigue respondiendo
perfectamente, asi que sin esto no se nota hasta que la guia esta vacia.
"""
from django.db import connection
from django.http import JsonResponse
from django.utils import timezone


def health(request):
    estado = {}
    ok = True

    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
        estado['base_de_datos'] = 'ok'
    except Exception as exc:
        estado['base_de_datos'] = f'error: {exc}'
        ok = False

    try:
        from django.core.cache import cache
        cache.set('health', 1, 10)
        estado['cache'] = 'ok' if cache.get('health') == 1 else 'no responde'
    except Exception as exc:
        estado['cache'] = f'error: {exc}'
        # La cache es un extra: que falle no deja el servicio inutilizable.

    try:
        from apps.epg.models import EpgSource, Program

        ultima = EpgSource.objects.filter(is_active=True).order_by('-last_update').first()
        if not ultima:
            estado['epg'] = 'sin fuentes configuradas'
        elif not ultima.last_update:
            estado['epg'] = 'nunca actualizado'
            ok = False
        else:
            horas = (timezone.now() - ultima.last_update).total_seconds() / 3600
            estado['epg'] = f'actualizado hace {horas:.1f} h'
            # Las fuentes se refrescan cada hora; 6 sin noticias es que el
            # worker de Celery no esta corriendo.
            if horas > 6:
                ok = False

        estado['programas_futuros'] = Program.objects.filter(
            start_time__gte=timezone.now()
        ).count()
    except Exception as exc:
        estado['epg'] = f'error: {exc}'
        ok = False

    try:
        from apps.pvr.models import Recording, RecordingStatus, StorageServer

        estado['grabando_ahora'] = Recording.objects.filter(
            status=RecordingStatus.RECORDING
        ).count()
        estado['grabaciones_programadas'] = Recording.objects.filter(
            status=RecordingStatus.SCHEDULED
        ).count()

        servidores = {}
        for servidor in StorageServer.objects.filter(is_active=True):
            if servidor.last_sync:
                minutos = (timezone.now() - servidor.last_sync).total_seconds() / 60
                servidores[servidor.name] = f'ultimo contacto hace {minutos:.0f} min'
                # tvarchivesync pregunta cada 5 min; 15 sin aparecer es que el
                # grabador esta parado.
                if servidor.records_archive and minutos > 15:
                    ok = False
            else:
                servidores[servidor.name] = 'nunca ha pedido tareas'
        estado['grabadores'] = servidores or 'ninguno configurado'
    except Exception as exc:
        estado['grabaciones'] = f'error: {exc}'
        ok = False

    estado['estado'] = 'ok' if ok else 'degradado'
    return JsonResponse(estado, status=200 if ok else 503)
