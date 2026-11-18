"""
Quien puede hacer que en el panel.

Hay dos clases de usuario del panel:
  - administrador (is_superuser): todo.
  - tecnico (is_staff sin is_superuser): clientes y decos, enteros. Crea,
    edita y borra clientes y decos, cambia la tarifa, recarga o reinicia un
    deco o todos, y manda firmware (pedido por Sergio el 18/11/2026: al
    principio no borraban). No entra en canales, tarifas, CDN, servidores,
    EPG o ajustes, ni crea otros tecnicos.

Se hace con una lista de paginas permitidas y no marcando las prohibidas: una
pagina nueva del panel queda cerrada para los tecnicos hasta que alguien la
apunte aqui, que es el fallo bueno.
"""
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect

TECNICO = {
    'dashboard', 'maquina',
    'users', 'user_create', 'user_edit', 'user_devices', 'user_renew', 'user_delete',
    'devices', 'device_create', 'device_edit', 'device_refresh_token',
    'device_evento', 'device_firmware', 'device_delete', 'devices_recargar_todos',
    'streams', 'logs',
}


def es_tecnico(user):
    return user.is_authenticated and user.is_staff and not user.is_superuser


class SoloAdministradores:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        donde = request.resolver_match
        if not donde or donde.namespace != 'portal' or not es_tecnico(request.user):
            return None
        if donde.url_name in TECNICO:
            return None
        aviso = 'Tu usuario de técnico no tiene permiso para eso.'
        pide_json = (request.headers.get('x-requested-with') == 'XMLHttpRequest'
                     or 'json' in request.headers.get('accept', '')
                     or (request.method == 'POST' and donde.url_name.endswith('_delete')))
        if pide_json:
            return JsonResponse({'status': 'error', 'error': aviso}, status=403)
        messages.error(request, aviso)
        return redirect('portal:dashboard')
