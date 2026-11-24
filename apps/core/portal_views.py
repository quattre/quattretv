"""
Portal admin views for QuattreTV.
"""
import json
from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Count, Q

from apps.accounts.models import User, Tariff
from apps.devices.models import Device
from .maquina import historia_maquina
from apps.channels.models import Channel, Category, ChannelStream


def get_base_stats():
    """Get base statistics for sidebar."""
    now = timezone.now()
    online_threshold = now - timedelta(minutes=5)

    return {
        'users_count': User.objects.count(),
        'devices_online': Device.objects.filter(last_seen__gte=online_threshold).count(),
        'channels_count': Channel.objects.filter(is_active=True).count(),
    }


@staff_member_required
def maquina(request):
    """CPU, memoria, disco y cola de peticiones del servidor, para el panel."""
    from .maquina import estado_maquina
    datos = estado_maquina()
    datos['decos'] = Device.objects.filter(
        last_seen__gte=timezone.now() - timedelta(minutes=5)).count()
    return JsonResponse(datos)


@staff_member_required
def dashboard(request):
    """Main dashboard view."""
    now = timezone.now()
    online_threshold = now - timedelta(minutes=5)

    # Statistics
    stats = {
        'users_count': User.objects.count(),
        # Activos: cuentas dadas de alta y sin la suscripcion caducada. Las que
        # vienen de Ministra no traen fecha, y contando solo las que tenian
        # fecha salia siempre "1 activos".
        'users_active': User.objects.filter(is_active=True).filter(
            Q(subscription_expires__isnull=True) | Q(subscription_expires__gte=now)
        ).count(),
        'devices_count': Device.objects.count(),
        'devices_online': Device.objects.filter(
            last_seen__gte=online_threshold
        ).count(),
        'channels_count': Channel.objects.filter(is_active=True).count(),
        'categories_count': Category.objects.count(),
        'streams_active': Device.objects.filter(
            last_seen__gte=online_threshold
        ).count(),
    }

    # Recent users
    recent_users = User.objects.select_related('tariff').order_by('-date_joined')[:5]

    # Online devices
    online_devices = Device.objects.filter(
        last_seen__gte=online_threshold
    ).select_related('user').order_by('-last_seen')[:5]

    # Canales mas vistos: en cual tiene puesto cada aparato conectado ahora
    # mismo. Antes eran los diez primeros por numero, con una barra de
    # "popularidad" que no existia y salia siempre gris.
    from django.db.models import Count
    viendo = list(Device.objects.filter(last_seen__gte=online_threshold)
                  .exclude(last_channel=None).values('last_channel')
                  .annotate(n=Count('id')).order_by('-n')[:10])
    canales = Channel.objects.select_related('category').in_bulk(
        [v['last_channel'] for v in viendo])
    tope = viendo[0]['n'] if viendo else 0
    top_channels = []
    for v in viendo:
        canal = canales.get(v['last_channel'])
        if canal:
            canal.viendo = v['n']
            canal.viendo_pct = max(3, round(100 * v['n'] / tope))
            top_channels.append(canal)

    # La grafica: muestras de cada 5 minutos que apuntan los latidos de los decos.
    historia = historia_maquina()

    # Aparatos por tipo (deco, app de LG, de Samsung, de Android), con la
    # cantidad en el rotulo, y debajo los decos por modelo.
    nombres_tipo = {'mag': 'Deco', 'lg': 'App LG', 'samsung': 'App Samsung',
                    'android': 'App Android'}
    orden_tipo = ['mag', 'lg', 'samsung', 'android']
    por_tipo = {d['device_type']: d['count'] for d in
                Device.objects.values('device_type').annotate(count=Count('id'))}
    tipos = [t for t in orden_tipo if t in por_tipo] + sorted(t for t in por_tipo if t not in orden_tipo)
    device_types_labels = ['%s (%d)' % (nombres_tipo.get(t, (t or 'Sin tipo').upper()), por_tipo[t]) for t in tipos]
    device_types_data = [por_tipo[t] for t in tipos]
    modelos_deco = list(Device.objects.filter(device_type='mag').values('model')
                        .annotate(count=Count('id')).order_by('-count'))

    # Los aparatos a los que se les ha cortado la conexion (apps/devices/cortes.py).
    from apps.devices import cortes

    context = {
        'active_page': 'dashboard',
        'stats': stats,
        'cortes': cortes.resumen(),
        'maquina_tarjetas': [('cpu', 'CPU'), ('carga', 'Carga'), ('mem', 'Memoria'),
                             ('disco', 'Disco'), ('red', 'Red')],
        'recent_users': recent_users,
        'online_devices': online_devices,
        'top_channels': top_channels,
        'historia': json.dumps(historia),
        'modelos_deco': modelos_deco,
        'device_types_labels': json.dumps(device_types_labels if device_types_labels else ['Sin datos']),
        'device_types_data': json.dumps(device_types_data if device_types_data else [1]),
    }
    context['stats'].update(get_base_stats())

    return render(request, 'portal/pages/dashboard.html', context)


@staff_member_required
def users_list(request):
    """
    Listado de CLIENTES.

    Antes salian mezclados los abonados y las cuentas de gestion, con el riesgo
    de editar o borrar por error la propia cuenta de administrador. Las cuentas
    de gestion se llevan desde el admin de Django, que es su sitio.
    """
    users = User.objects.filter(is_staff=False, is_superuser=False)
    users = users.select_related('tariff').prefetch_related('devices')

    # Filters
    search = request.GET.get('search')
    if search:
        users = users.filter(
            Q(username__icontains=search) |
            Q(first_name__icontains=search)
        )

    tariff_id = request.GET.get('tariff')
    if tariff_id:
        users = users.filter(tariff_id=tariff_id)

    status = request.GET.get('status')
    if status == 'active':
        users = users.filter(subscription_expires__gte=timezone.now())
    elif status == 'inactive':
        users = users.filter(is_active=False)
    elif status == 'expired':
        users = users.filter(subscription_expires__lt=timezone.now())

    users = users.order_by('-date_joined')

    # Pagination
    paginator = Paginator(users, 25)
    page = request.GET.get('page', 1)
    users = paginator.get_page(page)

    context = {
        'active_page': 'users',
        'stats': get_base_stats(),
        'users': users,
        'pagina': users,
        'paginas': _paginas(users),
        'consulta': _consulta_sin_pagina(request),
        'tariffs': Tariff.objects.filter(is_active=True),
    }

    return render(request, 'portal/pages/users.html', context)


@staff_member_required
def user_create(request):
    """Create new user."""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        tariff_id = request.POST.get('tariff')
        # Vacio = no caduca, como las cuentas que vienen de Ministra. Antes
        # salia 30 por defecto y un alta hecha con prisa se cortaba al mes.
        duration = request.POST.get('duration', '').strip()

        if User.objects.filter(username=username).exists():
            messages.error(request, 'El usuario ya existe')
            return redirect('portal:users')

        user = User.objects.create_user(
            username=username,
            password=password,
        )

        # Cuantos equipos puede tener lo marca la tarifa (limite_equipos), no
        # el alta: es lo que se factura.
        # El «nombre» de Ministra (alli iba el DNI): para encontrar al cliente.
        user.first_name = request.POST.get('nombre', '').strip()[:150]
        if tariff_id:
            user.tariff_id = tariff_id
        if duration.isdigit() and int(duration) > 0:
            user.subscription_expires = timezone.now() + timedelta(days=int(duration))
        user.save()

        messages.success(request, f'Usuario {username} creado correctamente')

    return redirect('portal:users')


@staff_member_required
def user_edit(request, user_id):
    """Edit user view."""
    user = get_object_or_404(User, id=user_id)

    if user.is_staff or user.is_superuser:
        messages.error(
            request,
            f'{user.username} es una cuenta de gestion, no un cliente. '
            'Se administra desde el admin de Django.'
        )
        return redirect('portal:users')

    if request.method == 'POST':
        user.first_name = request.POST.get('nombre', user.first_name).strip()[:150]
        user.tariff_id = request.POST.get('tariff') or None
        user.is_active = 'is_active' in request.POST
        # PIN parental: vacio = los canales de adultos no se bloquean.
        # Solo numeros: el navegador rellenaba esta casilla con el nombre del
        # tecnico (la tomaba por el usuario de la contraseña de al lado), y un
        # PIN "guillem" guardado sin querer dejaria al cliente sin poder abrir
        # los canales de adultos. Lo que no sean cifras no se guarda.
        pin = request.POST.get('parental_password', '').strip()
        if pin and not pin.isdigit():
            messages.error(request, 'El PIN parental solo puede llevar números; no se ha cambiado')
        else:
            user.parental_password = pin

        # Caducidad: vacio = no caduca nunca. Antes no habia forma de cambiarla
        # ni de quitarla desde el panel, solo sumar dias con el boton de renovar.
        caduca = request.POST.get('subscription_expires', '').strip()
        if caduca:
            from datetime import datetime
            try:
                dia = datetime.strptime(caduca, '%Y-%m-%d')
                user.subscription_expires = timezone.make_aware(
                    dia.replace(hour=23, minute=59, second=59))
            except ValueError:
                messages.error(request, 'La fecha de caducidad no es valida')
        else:
            user.subscription_expires = None

        # Handle password change
        new_password = request.POST.get('new_password', '').strip()
        if new_password:
            user.set_password(new_password)
            messages.success(request, 'Usuario y contrasena actualizados')
        else:
            messages.success(request, 'Usuario actualizado')

        user.save()
        return redirect('portal:users')

    context = {
        'active_page': 'users',
        'stats': get_base_stats(),
        'edit_user': user,
        'tariffs': Tariff.objects.filter(is_active=True),
    }

    return render(request, 'portal/pages/user_edit.html', context)


@staff_member_required
def user_renew(request, user_id):
    """Renew user subscription."""
    if request.method == 'POST':
        user = get_object_or_404(User, id=user_id)
        days = int(request.POST.get('days', 30))

        if user.subscription_expires and user.subscription_expires > timezone.now():
            user.subscription_expires += timedelta(days=days)
        else:
            user.subscription_expires = timezone.now() + timedelta(days=days)

        user.save()
        return JsonResponse({'status': 'ok'})

    return JsonResponse({'status': 'error'}, status=400)


@staff_member_required
def user_delete(request, user_id):
    """Delete user."""
    if request.method == 'POST':
        user = get_object_or_404(User, id=user_id)

        # Red de seguridad: desde el panel solo se borran clientes. Sin esto se
        # podia borrar la propia cuenta de administrador desde la lista.
        if user.pk == request.user.pk:
            return JsonResponse(
                {'status': 'error', 'error': 'No puedes borrar tu propia cuenta'},
                status=400)
        if user.is_staff or user.is_superuser:
            return JsonResponse(
                {'status': 'error',
                 'error': 'Es una cuenta de gestion. Se administra desde /admin/'},
                status=400)

        username = user.username
        user.delete()
        messages.success(request, f'Usuario {username} eliminado')
        return JsonResponse({'status': 'ok'})

    return JsonResponse({'status': 'error'}, status=400)


# ============== Tecnicos ==============
# Usuarios del panel con permisos recortados: ver apps/core/permisos.py. Estas
# tres paginas no estan en la lista de los tecnicos, asi que solo las abre un
# administrador.

@staff_member_required
def tecnicos_list(request):
    """Lista de tecnicos y alta de uno nuevo."""
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        nombre = request.POST.get('nombre', '').strip()
        password = request.POST.get('password', '')
        if not username or len(password) < 8:
            messages.error(request, 'Hace falta un usuario y una contraseña de 8 caracteres o más')
        elif User.objects.filter(username__iexact=username).exists():
            messages.error(request, f'Ya existe un usuario {username}')
        else:
            tecnico = User.objects.create_user(username=username, password=password)
            tecnico.first_name = nombre
            tecnico.is_staff = True
            tecnico.save()
            messages.success(request, f'Técnico {username} creado')
        return redirect('portal:tecnicos')

    context = {
        'active_page': 'tecnicos',
        'stats': get_base_stats(),
        'tecnicos': User.objects.filter(is_staff=True, is_superuser=False).order_by('username'),
        'administradores': User.objects.filter(is_superuser=True).order_by('username'),
    }
    return render(request, 'portal/pages/tecnicos.html', context)


@staff_member_required
def tecnico_edit(request, user_id):
    """Cambiar el nombre, la contraseña o apagar el acceso de un tecnico."""
    tecnico = get_object_or_404(User, id=user_id, is_staff=True, is_superuser=False)
    if request.method == 'POST':
        tecnico.first_name = request.POST.get('nombre', '').strip()
        tecnico.is_active = 'is_active' in request.POST
        password = request.POST.get('password', '')
        if password and len(password) < 8:
            messages.error(request, 'La contraseña tiene que tener 8 caracteres o más; no se ha cambiado')
        elif password:
            tecnico.set_password(password)
        tecnico.save()
        messages.success(request, f'Técnico {tecnico.username} actualizado')
    return redirect('portal:tecnicos')


@staff_member_required
def tecnico_delete(request, user_id):
    if request.method == 'POST':
        tecnico = get_object_or_404(User, id=user_id, is_staff=True, is_superuser=False)
        nombre = tecnico.username
        tecnico.delete()
        messages.success(request, f'Técnico {nombre} eliminado')
    return redirect('portal:tecnicos')


@staff_member_required
def user_devices(request, user_id):
    """View user devices."""
    user = get_object_or_404(User, id=user_id)
    devices = user.devices.all()

    context = {
        'active_page': 'users',
        'stats': get_base_stats(),
        'view_user': user,
        'devices': devices,
    }

    return render(request, 'portal/pages/user_devices.html', context)


# Devices views
@staff_member_required
def devices_list(request):
    """Devices list view."""
    if request.method == 'POST' and request.POST.get('device_id'):
        # El formulario de "Enviar mensaje". Antes no lo atendia nadie: se
        # rellenaba, se enviaba y no pasaba nada.
        from apps.devices import eventos
        device = get_object_or_404(Device, id=request.POST.get('device_id'))
        if request.POST.get('message_type') == 'reload':
            hecho = eventos.pedir(device, 'recargar')
        else:
            hecho = eventos.pedir_mensaje(device, request.POST.get('title', '').strip(),
                                          request.POST.get('message', '').strip())
        if hecho:
            messages.success(request, f'Enviado a {device.name or device.mac_address}: '
                                      'le llega en menos de un minuto si está encendido.')
        else:
            messages.error(request, 'No se ha podido enviar: la caché (Redis) no responde.')
        return redirect(request.get_full_path())

    now = timezone.now()
    online_threshold = now - timedelta(minutes=5)

    devices = Device.objects.select_related('user')

    # Stats
    stats = {
        'total': devices.count(),
        'online': devices.filter(last_seen__gte=online_threshold).count(),
        'mag': devices.filter(device_type='mag').count(),
        'apps': devices.filter(device_type__in=['android', 'ios']).count(),
    }

    # Filters
    search = request.GET.get('search')
    if search:
        devices = devices.filter(
            Q(mac_address__icontains=search) |
            Q(user__username__icontains=search) |
            Q(user__first_name__icontains=search) |
            Q(name__icontains=search) |
            # La IP desde la que se conecta (lo pidio soporte, 24/11/2026) y
            # el numero de serie de la etiqueta del deco.
            Q(last_ip__icontains=search.strip()) |
            Q(serial_number__icontains=search)
        )

    device_type = request.GET.get('type')
    if device_type:
        devices = devices.filter(device_type=device_type)

    status = request.GET.get('status')
    if status == 'online':
        devices = devices.filter(last_seen__gte=online_threshold)
    elif status == 'offline':
        devices = devices.exclude(last_seen__gte=online_threshold)
    elif status == 'activo':
        devices = devices.filter(is_active=True)
    elif status == 'inactivo':
        devices = devices.filter(is_active=False)
    orden = '-last_seen'
    if status == 'cortes':
        # Los que mas fallan, primero.
        from django.db.models import Case, IntegerField, Value, When
        from apps.devices import cortes
        cuantos = cortes.cuantos_24h()
        devices = devices.filter(id__in=list(cuantos)).annotate(n_cortes=Case(
            *[When(id=i, then=Value(n)) for i, n in cuantos.items()],
            default=Value(0), output_field=IntegerField()))
        orden = '-n_cortes' if cuantos else orden

    # Por paginas: con los ~950 aparatos y los ~1000 clientes del desplegable
    # en una sola pagina, esta pesaba 4 MB y tardaba casi 2 s en el servidor
    # (lento desde la oficina, 23/11/2026).
    pagina = Paginator(devices.order_by(orden, '-last_seen'), 50).get_page(request.GET.get('page'))
    devices = list(pagina.object_list)
    # La version de firmware de cada deco y si es la ultima de su modelo.
    from apps.devices import eventos
    firmwares = eventos.firmware_de_lista(devices)
    from apps.devices import cortes
    cortes_24h = cortes.de_lista(devices)
    for d in devices:
        d.fw = firmwares.get(d.id)
        d.cortes_24h = cortes_24h.get(d.id, 0)

    context = {
        'active_page': 'devices',
        'stats': {**get_base_stats(), **stats},
        'devices': devices,
        'pagina': pagina,
        'paginas': _paginas(pagina),
        'consulta': _consulta_sin_pagina(request),
    }

    return render(request, 'portal/pages/devices.html', context)


def _consulta_sin_pagina(request):
    """Los filtros de la lista, para que pasar de pagina no los pierda."""
    q = request.GET.copy()
    q.pop('page', None)
    return q.urlencode()


def _paginas(pagina):
    return pagina.paginator.get_elided_page_range(pagina.number, on_each_side=2, on_ends=1)


@staff_member_required
def buscar_usuarios(request):
    """
    Clientes que coinciden con lo escrito, para elegir el dueño de un aparato.
    Antes era un desplegable con los ~1000 clientes, sin poder buscar.
    """
    q = request.GET.get('q', '').strip()
    usuarios = User.objects.filter(is_staff=False, is_superuser=False)
    if q:
        usuarios = usuarios.filter(Q(username__icontains=q) | Q(first_name__icontains=q))
    usuarios = list(usuarios.order_by('username')[:60])
    b = q.lower()
    # Primero el que es exactamente eso, luego los que empiezan asi.
    usuarios.sort(key=lambda u: (u.username.lower() != b, not u.username.lower().startswith(b), u.username.lower()))
    return JsonResponse({'usuarios': [
        {'id': u.id, 'username': u.username, 'nombre': u.first_name} for u in usuarios[:20]
    ]})


@staff_member_required
def device_activo(request, device_id):
    """
    El interruptor de la lista. Un aparato desactivado deja de entrar: el
    portal le pide usuario y contraseña como si fuera nuevo.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error'}, status=405)
    device = get_object_or_404(Device, id=device_id)
    device.is_active = not device.is_active
    device.save()
    return JsonResponse({'status': 'ok', 'is_active': device.is_active})


@staff_member_required
def device_create(request):
    """Create new device."""
    if request.method == 'POST':
        mac_address = request.POST.get('mac_address', '').upper().replace('-', ':')
        user_id = request.POST.get('user')
        device_type = request.POST.get('device_type', 'mag')
        name = request.POST.get('name', '')

        if Device.objects.filter(mac_address=mac_address).exists():
            messages.error(request, 'Este MAC ya está registrado')
            return redirect('portal:devices')
        if not user_id or not User.objects.filter(id=user_id).exists():
            messages.error(request, 'Elige el cliente de la lista')
            return redirect('portal:devices')

        Device.objects.create(
            mac_address=mac_address,
            user_id=user_id,
            device_type=device_type,
            name=name,
            # Los decos MAG piden el video por el puerto de siempre (http):
            # con https los canales les salen en negro (el reproductor da
            # error al instante). Los importados de Ministra ya lo llevaban;
            # los dados de alta a mano en el panel no, y el primero que se
            # creo asi se quedo sin imagen (18/11/2026).
            usa_http_legacy=(device_type == 'mag'),
        )

        messages.success(request, f'Dispositivo {mac_address} creado')

    return redirect('portal:devices')


@staff_member_required
def device_edit(request, device_id):
    """Edit device."""
    device = get_object_or_404(Device, id=device_id)

    if request.method == 'POST':
        device.name = request.POST.get('name', '')
        # El tipo es lo que el aparato ES (deco, tele LG, movil): lo apunta el
        # propio aparato al darse de alta y de el cuelgan el firmware, las
        # ordenes y los canales que se le ocultan. Cambiarlo por error deja un
        # deco sin su parte de deco, asi que solo lo corrige un administrador.
        tipo = request.POST.get('device_type')
        if tipo and request.user.is_superuser:
            device.device_type = tipo
        device.user_id = request.POST.get('user') or device.user_id
        device.is_active = 'is_active' in request.POST
        device.save()
        messages.success(request, 'Dispositivo actualizado')
        return redirect('portal:devices')

    context = {
        'active_page': 'devices',
        'stats': get_base_stats(),
        'device': device,
    }
    from apps.devices import eventos
    context['firmware'] = eventos.firmware_para(device)
    context['fw_imagenes'] = eventos.imagenes_para(device)
    context['fw_prueba'] = eventos.prueba_de(device)
    context['fw_en_marcha'] = eventos.en_marcha(context['fw_prueba'])
    equipo = eventos.equipo_de(device)
    context['fw_equipo'] = equipo
    context['fw_lleva'] = eventos.que_lleva(equipo.get('desc')) if equipo else ''
    from apps.devices import cortes
    context['cortes'] = cortes.de(device)

    return render(request, 'portal/pages/device_edit.html', context)


@staff_member_required
def device_firmware(request, device_id):
    """
    Probar un firmware en un deco concreto (eventos.pedir_firmware): primero
    'comprobar' (el deco lee la imagen y cuenta al registro modelo, firma y
    version, sin tocar nada) y luego 'instalar'.
    """
    from apps.devices import eventos

    device = get_object_or_404(Device, id=device_id)
    if request.method == 'POST':
        url = request.POST.get('url', '').strip()
        instalar = request.POST.get('accion') == 'instalar'
        if device.device_type != 'mag':
            messages.error(request, 'El firmware solo se puede mandar a un deco MAG.')
        elif not url.startswith(('http://', 'https://')):
            messages.error(request, 'Pon la dirección completa de la imagen (http://...).')
        elif eventos.pedir_firmware(device, url, instalar=instalar):
            messages.success(request, ('Instalar' if instalar else 'Comprobar') +
                             ' firmware: el deco lo recoge en menos de un minuto si está encendido.')
        else:
            messages.error(request, 'No se ha podido apuntar la orden: la caché (Redis) no responde.')
    return redirect('portal:device_edit', device_id=device.id)


@staff_member_required
def device_evento(request, device_id):
    """Recargar el portal o reiniciar un aparato en su proximo latido."""
    from apps.devices import eventos

    device = get_object_or_404(Device, id=device_id)
    if request.method == 'POST':
        evento = request.POST.get('evento', '')
        if evento in eventos.EVENTOS:
            if eventos.pedir(device, evento):
                messages.success(request, f'{eventos.EVENTOS[evento]}: lo hará en menos de '
                                          'un minuto si está encendido, o al encenderse.')
            else:
                messages.error(request, 'No se ha podido apuntar la orden: la caché (Redis) no responde.')
    if request.POST.get('volver') == 'lista':
        return redirect('portal:devices')
    return redirect('portal:device_edit', device_id=device.id)


@staff_member_required
def devices_recargar_todos(request):
    """Recarga el portal de todos los decos, por ejemplo tras actualizarlo."""
    from apps.devices import eventos

    if request.method == 'POST':
        if eventos.pedir_recarga_general():
            messages.success(request, 'Todos los decos recargarán el portal en el próximo '
                                      'minuto. Las apps de las teles no se tocan.')
        else:
            messages.error(request, 'No se ha podido apuntar la orden: la caché (Redis) no responde.')
    return redirect('portal:devices')


@staff_member_required
def device_refresh_token(request, device_id):
    """Refresh device token."""
    if request.method == 'POST':
        device = get_object_or_404(Device, id=device_id)
        device.refresh_token()
        return JsonResponse({'status': 'ok', 'token': device.token})

    return JsonResponse({'status': 'error'}, status=400)


@staff_member_required
def device_delete(request, device_id):
    """Delete device."""
    if request.method == 'POST':
        device = get_object_or_404(Device, id=device_id)
        device.delete()
        return JsonResponse({'status': 'ok'})

    return JsonResponse({'status': 'error'}, status=400)


# Channels views
@staff_member_required
def channels_list(request):
    """Channels list view."""
    channels = Channel.objects.select_related('category').prefetch_related('streams')

    # Filters
    search = request.GET.get('search')
    if search:
        channels = channels.filter(name__icontains=search)

    category_id = request.GET.get('category')
    if category_id:
        channels = channels.filter(category_id=category_id)

    status = request.GET.get('status')
    if status == 'active':
        channels = channels.filter(is_active=True)
    elif status == 'inactive':
        channels = channels.filter(is_active=False)

    channels = channels.order_by('number')

    context = {
        'active_page': 'channels',
        'stats': get_base_stats(),
        'channels': channels,
        'categories': Category.objects.all(),
    }

    return render(request, 'portal/pages/channels.html', context)


@staff_member_required
def channel_create(request):
    """Create new channel."""
    if request.method == 'POST':
        name = request.POST.get('name')
        number = int(request.POST.get('number', 0))
        category_id = request.POST.get('category') or None
        stream_url = request.POST.get('stream_url')
        logo = request.POST.get('logo', '')
        epg_channel_id = request.POST.get('epg_channel_id', '')
        multicast_url = request.POST.get('multicast_url', '')
        is_hd = 'is_hd' in request.POST
        is_adult = 'is_adult' in request.POST
        has_archive = 'has_archive' in request.POST

        # Los campos del modelo son epg_id / has_catchup / logo_url: pasar
        # epg_channel_id o has_archive a create() reventaba con TypeError.
        channel = Channel.objects.create(
            name=name,
            number=number,
            category_id=category_id,
            logo_url=logo,
            stream_url=stream_url or '',
            epg_id=epg_channel_id,
            multicast_url=multicast_url,
            is_hd=is_hd,
            is_adult=is_adult,
            has_catchup=has_archive,
            has_timeshift=has_archive,
        )

        if stream_url:
            ChannelStream.objects.create(
                channel=channel,
                url=stream_url,
                name='Principal',
                priority=100,
            )

        messages.success(request, f'Canal {name} creado')

    return redirect('portal:channels')


@staff_member_required
def channel_edit(request, channel_id):
    """Edit channel."""
    channel = get_object_or_404(Channel, id=channel_id)

    if request.method == 'POST':
        channel.name = request.POST.get('name')
        channel.number = int(request.POST.get('number', 0))
        channel.category_id = request.POST.get('category') or None
        channel.logo_url = request.POST.get('logo', '')
        # epg_channel_id / has_archive no existen en el modelo: asignarlos era
        # crear atributos fantasma que se perdian al guardar, y por eso no habia
        # forma de mapear el EPG a mano desde el portal.
        channel.epg_id = request.POST.get('epg_channel_id', '')
        channel.multicast_url = request.POST.get('multicast_url', '')
        desfase = request.POST.get('desfase_archivo', '0').strip()
        channel.desfase_archivo = int(desfase) if desfase.lstrip('-').isdigit() else 0
        channel.is_hd = 'is_hd' in request.POST
        channel.is_adult = 'is_adult' in request.POST
        channel.has_catchup = 'has_archive' in request.POST
        channel.has_timeshift = 'has_archive' in request.POST
        channel.is_active = 'is_active' in request.POST
        # En que aparatos NO se ve. La tarifa dice que canales tiene el CLIENTE;
        # esto dice en que aparatos se pueden ver, que no es lo mismo: un mismo
        # cliente puede tener un MAG en el salon y una LG en la habitacion.
        channel.oculto_para = Channel.marca(request.POST.getlist('oculto_para'))

        # Update stream URL (both in Channel and ChannelStream)
        stream_url = request.POST.get('stream_url')
        if stream_url:
            channel.stream_url = stream_url
        channel.save()

        if stream_url:
            # Get or create the primary stream (highest priority)
            stream = channel.streams.order_by('-priority').first()
            if stream:
                stream.url = stream_url
                stream.save()
            else:
                ChannelStream.objects.create(
                    channel=channel,
                    url=stream_url,
                    name='Principal',
                    priority=100,
                )

        messages.success(request, 'Canal actualizado')
        return redirect('portal:channels')

    from apps.devices.models import DeviceType
    context = {
        'active_page': 'channels',
        'stats': get_base_stats(),
        'channel': channel,
        'categories': Category.objects.all(),
        'tipos_aparato': DeviceType.choices,
        'ocultos': channel.tipos_ocultos,
        'ocultos_nombres': [dict(DeviceType.choices).get(t, t) for t in channel.tipos_ocultos],
    }

    return render(request, 'portal/pages/channel_edit.html', context)


@staff_member_required
def channel_delete(request, channel_id):
    """Delete channel."""
    if request.method == 'POST':
        channel = get_object_or_404(Channel, id=channel_id)
        channel.delete()
        return JsonResponse({'status': 'ok'})

    return JsonResponse({'status': 'error'}, status=400)


@staff_member_required
def channels_import(request):
    """Import channels from M3U/M3U8."""
    if request.method == 'POST':
        m3u_file = request.FILES.get('m3u_file')
        m3u_text = request.POST.get('m3u_text', '').strip()

        if not m3u_file and not m3u_text:
            messages.error(request, 'Debes subir un archivo M3U o pegar el contenido')
            return redirect('portal:channels_import')

        # Get content
        if m3u_file:
            raw_content = m3u_file.read()
            try:
                content = raw_content.decode('utf-8')
            except UnicodeDecodeError:
                content = raw_content.decode('latin-1')
        else:
            content = m3u_text

        # Parse M3U
        channels_data = parse_m3u(content)

        if not channels_data:
            messages.error(request, 'No se encontraron canales válidos en el archivo')
            return redirect('portal:channels_import')

        # Import channels
        created = 0
        updated = 0
        errors = 0

        # Get import type from form (tv or radio)
        import_type = request.POST.get('import_type', 'tv')
        is_radio_import = (import_type == 'radio')

        # Get current max numbers for TV and Radio
        # TV starts at 1, Radio starts at 1001 to avoid conflicts (number field is unique)
        max_tv_number = Channel.objects.filter(is_radio=False).order_by('-number').values_list('number', flat=True).first() or 0
        max_radio_number = Channel.objects.filter(is_radio=True).order_by('-number').values_list('number', flat=True).first() or 1000

        for ch_data in channels_data:
            try:
                # Get or create category
                category = None
                if ch_data.get('group'):
                    category, _ = Category.objects.get_or_create(
                        name=ch_data['group'],
                        defaults={
                            'alias': slugify(ch_data['group']),
                            'is_active': True
                        }
                    )

                # Use the import type selected by the user (TV or Radio button)
                is_radio = is_radio_import

                # Check if channel exists (by epg_id or name)
                existing = None

                # Try by epg_id first
                if ch_data.get('tvg_id'):
                    existing = Channel.objects.filter(epg_id=ch_data['tvg_id']).first()

                # Then try by name (exact match)
                if not existing:
                    existing = Channel.objects.filter(name__iexact=ch_data['name']).first()

                if existing:
                    # Update existing channel
                    existing.stream_url = ch_data['url']
                    if ch_data.get('logo'):
                        existing.logo_url = ch_data['logo']
                    if category:
                        existing.category = category
                    if ch_data.get('tvg_id'):
                        existing.epg_id = ch_data['tvg_id']
                    existing.is_hd = 'HD' in ch_data['name'].upper() or '1080' in ch_data['name']
                    existing.is_4k = '4K' in ch_data['name'].upper() or 'UHD' in ch_data['name'].upper()
                    existing.is_radio = is_radio
                    existing.save()

                    # Update or create stream
                    stream = existing.streams.order_by('-priority').first()
                    if stream:
                        stream.url = ch_data['url']
                        stream.save()
                    else:
                        ChannelStream.objects.create(
                            channel=existing,
                            url=ch_data['url'],
                            name='Principal',
                            priority=100,
                        )
                    updated += 1
                else:
                    # Create new channel with correlative number
                    if is_radio:
                        max_radio_number += 1
                        new_number = max_radio_number
                    else:
                        max_tv_number += 1
                        new_number = max_tv_number

                    channel = Channel.objects.create(
                        name=ch_data['name'],
                        number=new_number,
                        stream_url=ch_data['url'],
                        logo_url=ch_data.get('logo', ''),
                        category=category,
                        epg_id=ch_data.get('tvg_id', ''),
                        is_hd='HD' in ch_data['name'].upper() or '1080' in ch_data['name'],
                        is_4k='4K' in ch_data['name'].upper() or 'UHD' in ch_data['name'].upper(),
                        is_radio=is_radio,
                        is_active=True
                    )
                    # Create stream
                    ChannelStream.objects.create(
                        channel=channel,
                        url=ch_data['url'],
                        name='Principal',
                        priority=100,
                    )
                    created += 1

            except Exception as e:
                errors += 1

        messages.success(request, f'Importación completada: {len(channels_data)} parseados, {created} creados, {updated} actualizados, {errors} errores')
        return redirect('portal:channels')

    # GET request - show import form
    context = {
        'active_page': 'channels',
        'stats': get_base_stats(),
    }
    return render(request, 'portal/pages/channels_import.html', context)


def parse_m3u(content):
    """Parse M3U/M3U8 content and extract channel data."""
    import re

    channels = []
    # Handle both Windows (\r\n) and Unix (\n) line endings
    content = content.replace('\r\n', '\n').replace('\r', '\n')
    lines = content.strip().split('\n')

    current_channel = None

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if line.startswith('#EXTINF:'):
            # Parse EXTINF line
            current_channel = {}

            # Extract attributes
            # tvg-id
            tvg_id_match = re.search(r'tvg-id="([^"]*)"', line)
            if tvg_id_match:
                current_channel['tvg_id'] = tvg_id_match.group(1)

            # tvg-chno (channel number)
            tvg_chno_match = re.search(r'tvg-chno="([^"]*)"', line)
            if tvg_chno_match:
                try:
                    current_channel['number'] = int(tvg_chno_match.group(1))
                except ValueError:
                    pass

            # tvg-name
            tvg_name_match = re.search(r'tvg-name="([^"]*)"', line)
            if tvg_name_match:
                current_channel['tvg_name'] = tvg_name_match.group(1)

            # tvg-logo
            logo_match = re.search(r'tvg-logo="([^"]*)"', line)
            if logo_match:
                current_channel['logo'] = logo_match.group(1)

            # group-title
            group_match = re.search(r'group-title="([^"]*)"', line)
            if group_match:
                current_channel['group'] = group_match.group(1)

            # Channel name (after the last comma)
            name_match = re.search(r',\s*(.+)$', line)
            if name_match:
                current_channel['name'] = name_match.group(1).strip()
            elif tvg_name_match:
                current_channel['name'] = tvg_name_match.group(1)

        elif line and not line.startswith('#') and current_channel:
            # This is the URL line - clean Stalker "ffmpeg " prefix if present
            url = line
            if url.startswith('ffmpeg '):
                url = url[7:]  # Remove "ffmpeg " prefix
            current_channel['url'] = url
            if current_channel.get('name') and current_channel.get('url'):
                channels.append(current_channel)
            current_channel = None

    return channels


def slugify(text):
    """Simple slugify function."""
    import re
    text = text.lower()
    text = re.sub(r'[áàäâ]', 'a', text)
    text = re.sub(r'[éèëê]', 'e', text)
    text = re.sub(r'[íìïî]', 'i', text)
    text = re.sub(r'[óòöô]', 'o', text)
    text = re.sub(r'[úùüû]', 'u', text)
    text = re.sub(r'[ñ]', 'n', text)
    text = re.sub(r'[^a-z0-9]+', '-', text)
    text = text.strip('-')
    return text or 'sin-categoria'


# Categories
@staff_member_required
def categories_list(request):
    """Categories list."""
    categories = Category.objects.annotate(channels_count=Count('channels'))

    context = {
        'active_page': 'categories',
        'stats': get_base_stats(),
        'categories': categories,
    }

    return render(request, 'portal/pages/categories.html', context)


# Tariffs
@staff_member_required
def tariffs_list(request):
    """Tariffs list."""
    tariffs = Tariff.objects.prefetch_related('channels').annotate(users_count=Count('users'))
    categories = Category.objects.prefetch_related('channels').all()
    uncategorized_channels = Channel.objects.filter(category__isnull=True)

    context = {
        'active_page': 'tariffs',
        'stats': get_base_stats(),
        'tariffs': tariffs,
        'categories': categories,
        'uncategorized_channels': uncategorized_channels,
    }

    return render(request, 'portal/pages/tariffs.html', context)


@staff_member_required
def tariff_create(request):
    """Create new tariff."""
    if request.method == 'POST':
        tariff = Tariff.objects.create(
            name=request.POST.get('name'),
            duration_days=int(request.POST.get('duration_days', 0)),
            max_devices=int(request.POST.get('max_devices', 5)),
            max_concurrent_streams=int(request.POST.get('max_concurrent_streams', 2)),
            has_timeshift='has_timeshift' in request.POST,
            has_catchup='has_catchup' in request.POST,
            has_vod='has_vod' in request.POST,
            has_pvr='has_pvr' in request.POST,
        )

        # Añadir canales seleccionados
        channel_ids = request.POST.getlist('channels')
        if channel_ids:
            tariff.channels.set(channel_ids)

        messages.success(request, f'Tarifa {tariff.name} creada con {tariff.channels.count()} canales')

    return redirect('portal:tariffs')


@staff_member_required
def tariff_edit(request, tariff_id):
    """Edit tariff."""
    tariff = get_object_or_404(Tariff, id=tariff_id)

    if request.method == 'POST':
        tariff.name = request.POST.get('name')
        tariff.duration_days = int(request.POST.get('duration_days', 0))
        tariff.max_devices = int(request.POST.get('max_devices', 5))
        tariff.max_concurrent_streams = int(request.POST.get('max_concurrent_streams', 2))
        tariff.has_timeshift = 'has_timeshift' in request.POST
        tariff.has_catchup = 'has_catchup' in request.POST
        tariff.has_vod = 'has_vod' in request.POST
        tariff.has_pvr = 'has_pvr' in request.POST
        tariff.is_active = 'is_active' in request.POST
        tariff.save()

        # Actualizar canales
        channel_ids = request.POST.getlist('channels')
        tariff.channels.set(channel_ids)

        messages.success(request, 'Tarifa actualizada')
        return redirect('portal:tariffs')

    categories = Category.objects.prefetch_related('channels').all()
    uncategorized_channels = Channel.objects.filter(category__isnull=True)

    context = {
        'active_page': 'tariffs',
        'stats': get_base_stats(),
        'tariff': tariff,
        'categories': categories,
        'uncategorized_channels': uncategorized_channels,
    }

    return render(request, 'portal/pages/tariff_edit.html', context)


@staff_member_required
def tariff_delete(request, tariff_id):
    """Delete tariff."""
    if request.method == 'POST':
        tariff = get_object_or_404(Tariff, id=tariff_id)
        tariff.delete()
        return JsonResponse({'status': 'ok'})

    return JsonResponse({'status': 'error'}, status=400)


# Servidores
@staff_member_required
def servidores_list(request):
    """Estado de las máquinas: disco, memoria, carga y qué lleva cada una."""
    from apps.channels.models import CdnServer
    from apps.channels import cdn as cdn_tools
    from apps.core import monitoring
    from apps.pvr.models import Recording, RecordingStatus, StorageServer

    peticiones = []
    contexto_extra = {}

    for servidor in CdnServer.objects.filter(is_active=True):
        clave = f'cdn:{servidor.id}'
        peticiones.append((clave, servidor.ssh_host, servidor.ssh_port,
                           servidor.ssh_user, 'CDN'))
        contexto_extra[clave] = {
            'titulo': servidor.name,
            'detalle': cdn_tools.resumen_cdn(servidor),
            'tipo': 'cdn',
        }

    for servidor in StorageServer.objects.filter(is_active=True):
        clave = f'sto:{servidor.id}'
        peticiones.append((clave, servidor.ssh_host, servidor.ssh_port,
                           servidor.ssh_user, servidor.get_role_display()))
        contexto_extra[clave] = {
            'titulo': servidor.name,
            'detalle': {
                'ultimo_contacto': servidor.last_sync,
                'grabando': Recording.objects.filter(
                    storage=servidor, status=RecordingStatus.RECORDING
                ).count(),
            },
            'tipo': 'storage',
        }

    metricas = monitoring.estado_de_varios(peticiones)
    for metrica in metricas:
        metrica.update(contexto_extra.get(metrica['nombre'], {}))

    con_avisos = sum(1 for m in metricas if m.get('avisos') or not m.get('ok'))

    context = {
        'active_page': 'servidores',
        'stats': get_base_stats(),
        'servidores': metricas,
        'con_avisos': con_avisos,
    }
    return render(request, 'portal/pages/servidores.html', context)


# Grabaciones
@staff_member_required
def grabaciones(request):
    """
    Archivo de catchup y grabaciones de clientes, de las dos plataformas.

    Mientras conviva con Ministra se ve todo, se toque o no desde aqui: lo que
    graba Ministra se lee del disco y de la copia de cada noche, y lo que graba
    la plataforma nueva sale de sus propias fichas.
    """
    from apps.pvr import archivo
    from apps.pvr.models import Recording, RecordingStatus, StorageServer

    if request.method == 'POST':
        # Dos interruptores por canal: si los clientes ven su catchup y si lo
        # pueden grabar. Los dos se aplican al momento, sin tocar el grabador.
        canal = get_object_or_404(Channel, id=request.POST.get('channel_id'))
        campo = request.POST.get('campo')
        nombres = {'has_catchup': 'Catchup', 'has_recording': 'Grabar'}
        if campo in nombres:
            setattr(canal, campo, not getattr(canal, campo))
            canal.save(update_fields=[campo])
            messages.success(request, f'{nombres[campo]} en {canal.name}: '
                                      f'{"activado" if getattr(canal, campo) else "desactivado"}.')
        return redirect(request.get_full_path())

    grabadores = list(StorageServer.objects.filter(is_active=True))
    for grabador in grabadores:
        grabador.n_grabando = Recording.objects.filter(
            storage=grabador, status=RecordingStatus.RECORDING).count()
        grabador.n_guardadas = Recording.objects.filter(
            storage=grabador, status=RecordingStatus.COMPLETED).count()

    # El archivo en TS es el de Ministra: sus carpetas van por el id de alli.
    de_archivo = next((g for g in grabadores if g.records_archive and g.ssh_host), None)
    en_disco = archivo.ventanas(de_archivo)
    canales = list(Channel.objects.filter(is_radio=False).order_by('number'))
    for canal in canales:
        canal.ventana = (en_disco or {}).get(canal.ministra_id or canal.id)
        canal.interruptores = [('has_catchup', canal.has_catchup),
                               ('has_recording', canal.has_recording)]

    grabaciones = Recording.objects.select_related('user', 'channel', 'storage')
    q = request.GET.get('q', '').strip()
    if q:
        grabaciones = grabaciones.filter(
            Q(user__username__icontains=q) | Q(title__icontains=q) | Q(channel__name__icontains=q))
    origen = request.GET.get('origen', '')
    if origen == 'ministra':
        grabaciones = grabaciones.exclude(ministra_id=None)
    elif origen == 'nueva':
        grabaciones = grabaciones.filter(ministra_id=None)
    estado = request.GET.get('estado', '')
    if estado:
        grabaciones = grabaciones.filter(status=estado)

    pagina = Paginator(grabaciones.order_by('-start_time'), 50).get_page(request.GET.get('page'))
    resumen = {
        'ministra': Recording.objects.exclude(ministra_id=None).count(),
        'nueva': Recording.objects.filter(ministra_id=None).count(),
        'clientes': Recording.objects.values('user').distinct().count(),
        'grabando': Recording.objects.filter(status=RecordingStatus.RECORDING).count(),
        'programadas': Recording.objects.filter(status=RecordingStatus.SCHEDULED).count(),
    }

    context = {
        'active_page': 'grabaciones',
        'stats': get_base_stats(),
        'grabadores': grabadores,
        'canales': canales,
        'archivo_visto': en_disco is not None,
        'de_archivo': de_archivo,
        'canales_con_archivo': sum(1 for c in canales if c.ventana),
        'pagina': pagina,
        'resumen': resumen,
        'estados': RecordingStatus.choices,
        'filtros': {'q': q, 'origen': origen, 'estado': estado},
    }
    return render(request, 'portal/pages/grabaciones.html', context)


# CDNs
# Ultimos 7 dias
@staff_member_required
def ultimos7(request):
    """
    Lo que ven los decos en "Ultimos 7 dias", y las correcciones a mano.

    El tipo de cada programa se adivina con la guia y a veces falla. Aqui se
    quita una fila entera, se pasa un titulo a otra fila, se oculta o se le
    pone caratula. Todo vale para todas sus emisiones y se aplica al momento.
    """
    from types import SimpleNamespace
    from django.conf import settings
    from apps.epg.models import FilaSemana, TituloSemana
    from apps.stalker_api import semana

    nombres = dict(semana.GRUPOS)
    if request.method == 'POST':
        accion = request.POST.get('accion')
        if accion == 'fila' and request.POST.get('grupo') in nombres:
            fila, _ = FilaSemana.objects.get_or_create(grupo=request.POST['grupo'])
            fila.visible = not fila.visible
            fila.save(update_fields=['visible'])
            messages.success(request, f'Fila {nombres[fila.grupo]}: '
                                      f'{"se ve" if fila.visible else "oculta"}.')
        elif accion == 'titulo':
            titulo = request.POST.get('titulo', '').strip()
            grupo = request.POST.get('grupo', '')
            grupo = grupo if grupo in nombres else ''
            oculto = request.POST.get('oculto') == '1'
            imagen = request.POST.get('imagen', '').strip()
            clave = semana.plano(titulo)
            if imagen and not imagen.startswith(('http://', 'https://')):
                messages.error(request, 'La carátula tiene que ser una dirección http(s).')
            elif clave:
                # Sin nada que corregir, la ficha sobra: vuelve a ser automatico.
                if not (grupo or oculto or imagen):
                    TituloSemana.objects.filter(clave=clave).delete()
                else:
                    TituloSemana.objects.update_or_create(clave=clave, defaults={
                        'titulo': titulo, 'grupo': grupo, 'oculto': oculto, 'imagen': imagen})
                messages.success(request, f'«{titulo}» corregido.')
        elif accion == 'deshacer':
            TituloSemana.objects.filter(id=request.POST.get('id')).delete()
            messages.success(request, 'Corrección quitada: vuelve a ser automático.')
        elif accion == 'caratulas':
            from apps.epg.tasks import buscar_caratulas
            buscar_caratulas.delay()
            messages.success(request, 'Buscando las carátulas que faltan. Tarda unos minutos.')
        semana.invalidar()
        return redirect(request.get_full_path())

    # Lo que veria un deco cualquiera con todo contratado.
    deco = SimpleNamespace(device_type='mag', user=SimpleNamespace(tariff=None))
    canales = semana.canales_con_archivo(deco)
    ocultas, _ = semana.correcciones()
    corregidos = {t.clave: t for t in TituloSemana.objects.all()}
    filas = semana.filas_de(semana.emisiones(canales), por_grupo=None)
    for fila in filas:
        fila['visible'] = fila['id'] not in ocultas
        fila['total'] = len(fila['items'])
        fila['sin_imagen'] = sum(1 for i in fila['items'] if not i['img'])
        for item in fila['items']:
            item['correccion'] = corregidos.get(semana.plano(item['titulo']))
            item['inicio'] = timezone.datetime.fromtimestamp(item['ini'], tz=timezone.get_default_timezone())

    context = {
        'active_page': 'ultimos7',
        'filas': filas,
        'grupos': semana.GRUPOS,
        'n_canales': len(canales),
        'correcciones': list(corregidos.values()),
        'nombres': nombres,
        'tmdb': bool(settings.QUATTRETV.get('TMDB_API_KEY')),
    }
    return render(request, 'portal/pages/ultimos7.html', context)


@staff_member_required
def cdns_list(request):
    """Panel de CDNs: qué canales lleva cada uno y cuáles están emitiendo."""
    from apps.channels.models import CdnServer
    from apps.channels import cdn as cdn_tools

    if request.method == 'POST':
        nombre = request.POST.get('name', '').strip()
        hls = request.POST.get('hls_base_url', '').strip()
        if not nombre or not hls:
            messages.error(request, 'Nombre y URL base del HLS son obligatorios')
        else:
            CdnServer.objects.create(
                name=nombre,
                hls_base_url=hls,
                ssh_host=request.POST.get('ssh_host', '').strip(),
                ssh_port=int(request.POST.get('ssh_port') or 22),
                ssh_user=request.POST.get('ssh_user', '').strip() or 'quattre',
            )
            messages.success(request, f'CDN {nombre} añadido')
        return redirect('portal:cdns')

    servidores = []
    for servidor in CdnServer.objects.all():
        canales = list(servidor.channels.filter(is_active=True).order_by('number'))
        estados = cdn_tools.estados_de(canales)
        for canal in canales:
            canal.estado = estados.get(canal.id, {})
        servidores.append({
            'cdn': servidor,
            'canales': canales,
            'resumen': cdn_tools.resumen_cdn(servidor, estados),
        })

    context = {
        'active_page': 'cdns',
        'stats': get_base_stats(),
        'servidores': servidores,
        'sin_cdn': Channel.objects.filter(is_active=True, cdn__isnull=True).count(),
    }
    return render(request, 'portal/pages/cdns.html', context)


@staff_member_required
def cdn_delete(request, cdn_id):
    """Quitar un CDN. Los canales se quedan sin asignar, no se borran."""
    from apps.channels.models import CdnServer

    servidor = get_object_or_404(CdnServer, id=cdn_id)
    nombre = servidor.name
    servidor.delete()
    messages.success(request, f'CDN {nombre} eliminado. Sus canales quedan sin asignar.')
    return redirect('portal:cdns')


@staff_member_required
def cdn_detect(request, cdn_id):
    """
    Asignar a este CDN los canales cuya URL apunta a él.

    Evita tener que emparejar 50 canales a mano: el dato ya está en la URL del
    stream.
    """
    from urllib.parse import urlparse

    from apps.channels.models import CdnServer
    from apps.channels import cdn as cdn_tools

    servidor = get_object_or_404(CdnServer, id=cdn_id)
    host = urlparse(servidor.hls_base_url).hostname or ''
    if not host:
        messages.error(request, 'La URL base del CDN no tiene un host válido')
        return redirect('portal:cdns')

    asignados = 0
    for canal in Channel.objects.filter(is_active=True):
        if host not in (canal.stream_url or ''):
            continue
        canal.cdn = servidor
        if not canal.cdn_name:
            canal.cdn_name = cdn_tools.nombre_en_cdn(canal)
        canal.save(update_fields=['cdn', 'cdn_name'])
        asignados += 1

    messages.success(request, f'{asignados} canales asignados a {servidor.name}')
    return redirect('portal:cdns')


@staff_member_required
def cdn_channel_restart(request, channel_id):
    """Reiniciar la emisión de un canal en su CDN."""
    from apps.channels import cdn as cdn_tools

    canal = get_object_or_404(Channel, id=channel_id)
    ok, mensaje = cdn_tools.reiniciar_canal(canal)
    if ok:
        messages.success(request, mensaje)
    else:
        messages.error(request, mensaje)
    return redirect('portal:cdns')


# EPG
@staff_member_required
def epg_list(request):
    """EPG sources list and creation."""
    from apps.epg.models import EpgSource, Program

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        url = request.POST.get('url', '').strip()
        try:
            # El formulario pide horas; el modelo guarda segundos.
            interval = int(request.POST.get('update_interval', 24)) * 3600
        except ValueError:
            interval = 24 * 3600

        if not name or not url:
            messages.error(request, 'Nombre y URL son obligatorios')
        else:
            EpgSource.objects.create(
                name=name,
                url=url,
                update_interval=interval,
                is_active=True,
                auto_update=True,
            )
            messages.success(request, f'Fuente EPG {name} creada')
        return redirect('portal:epg')

    mapped = Channel.objects.filter(is_active=True).exclude(epg_id='').count()
    unmapped = Channel.objects.filter(is_active=True, epg_id='').count()

    context = {
        'active_page': 'epg',
        'stats': get_base_stats(),
        'sources': EpgSource.objects.all(),
        'programs_count': Program.objects.count(),
        'mapped_channels': mapped,
        'unmapped_channels': unmapped,
    }

    return render(request, 'portal/pages/epg.html', context)


@staff_member_required
def epg_source_update(request, source_id):
    """Trigger an EPG refresh for one source."""
    from apps.epg.models import EpgSource
    from apps.epg.tasks import update_epg_source

    source = get_object_or_404(EpgSource, id=source_id)

    try:
        update_epg_source.delay(source.id)
        messages.success(request, f'Actualizacion de {source.name} encolada')
    except Exception as exc:
        # Sin worker de Celery no hay quien la ejecute: decirlo claramente en
        # vez de fingir que se ha encolado.
        messages.error(
            request,
            f'No se pudo encolar la actualizacion ({exc}). '
            'Revisa que el worker de Celery este arrancado.'
        )

    return redirect('portal:epg')


@staff_member_required
def epg_source_delete(request, source_id):
    """Delete an EPG source."""
    from apps.epg.models import EpgSource

    source = get_object_or_404(EpgSource, id=source_id)
    name = source.name
    source.delete()
    messages.success(request, f'Fuente EPG {name} eliminada')
    return redirect('portal:epg')


@staff_member_required
def epg_source_toggle(request, source_id):
    """Enable/disable an EPG source."""
    from apps.epg.models import EpgSource

    source = get_object_or_404(EpgSource, id=source_id)
    source.is_active = not source.is_active
    source.save(update_fields=['is_active'])
    messages.success(
        request,
        f'Fuente {source.name} {"activada" if source.is_active else "desactivada"}'
    )
    return redirect('portal:epg')


# VOD
@staff_member_required
def vod_list(request):
    """VOD list."""
    from apps.vod.models import Movie, Series

    movies = Movie.objects.count()
    series = Series.objects.count()

    context = {
        'active_page': 'vod',
        'stats': get_base_stats(),
        'movies_count': movies,
        'series_count': series,
    }

    return render(request, 'portal/pages/vod.html', context)


# Streams
@staff_member_required
def streams_list(request):
    """Active streams list."""
    now = timezone.now()
    online_threshold = now - timedelta(minutes=5)

    active_devices = Device.objects.filter(
        last_seen__gte=online_threshold
    ).select_related('user', 'last_channel')

    context = {
        'active_page': 'streams',
        'stats': get_base_stats(),
        'active_devices': active_devices,
    }

    return render(request, 'portal/pages/streams.html', context)


# Logs
@staff_member_required
def logs_list(request):
    """Logs view."""
    context = {
        'active_page': 'logs',
        'stats': get_base_stats(),
    }

    return render(request, 'portal/pages/logs.html', context)


PERIODOS_CORTES = [('24h', 'Últimas 24 h', 1), ('7d', 'Últimos 7 días', 7),
                   ('30d', 'Últimos 30 días', 30), ('todo', 'Todo', None)]


@staff_member_required
def cortes_list(request):
    """
    El registro de cortes de conexion de todos los aparatos (lo pidio soporte,
    24/11/2026): quien, cuando, cuanto y desde que IP, y los que mas tienen.
    """
    from apps.devices import cortes
    from apps.devices.models import CorteConexion

    periodo = request.GET.get('periodo', '7d')
    dias = dict((p, d) for p, _, d in PERIODOS_CORTES).get(periodo, 7)
    qs = CorteConexion.objects.select_related('device', 'device__user')
    if dias:
        qs = qs.filter(inicio__gte=timezone.now() - timedelta(days=dias))
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(Q(device__mac_address__icontains=q) | Q(ip__icontains=q) |
                       Q(device__user__username__icontains=q) | Q(device__name__icontains=q))
    solo = request.GET.get('solo') == '1'
    if solo:
        qs = cortes.contables(qs)

    pagina = Paginator(qs, 100).get_page(request.GET.get('page'))
    ahora = timezone.now()
    context = {
        'active_page': 'cortes',
        'stats': get_base_stats(),
        'filas': [cortes.fila(c, ahora) for c in pagina.object_list],
        'pagina': pagina,
        'paginas': _paginas(pagina),
        'consulta': _consulta_sin_pagina(request),
        'periodos': PERIODOS_CORTES,
        'periodo': periodo,
        'q': q,
        'solo': solo,
        'los_que_mas': cortes.los_que_mas(qs),
        'total': qs.count(),
        'cuentan': cortes.contables(qs).count(),
        'generales': cortes.generales(timezone.now() - timedelta(days=dias or 3650)),
        'minimo': cortes.MINIMO,
    }
    return render(request, 'portal/pages/cortes.html', context)


# Settings
@staff_member_required
def settings_view(request):
    """Settings view."""
    from django.conf import settings
    from apps.epg.models import FuenteCaratula

    if request.method == 'POST' and request.POST.get('accion') == 'caratulas':
        for f in FuenteCaratula.objects.all():
            f.activa = ('activa_%d' % f.id) in request.POST
            orden = request.POST.get('orden_%d' % f.id, '')
            f.orden = int(orden) if orden.isdigit() else f.orden
            clave = request.POST.get('clave_%d' % f.id)
            # La clave no se enseña: vacio es "no tocar", y para borrarla un guion.
            if clave == '-':
                f.clave = ''
            elif clave:
                f.clave = clave.strip()[:300]
            f.save(update_fields=['activa', 'orden', 'clave'])
        messages.success(request, 'Fuentes de carátulas guardadas')
        if 'buscar' in request.POST:
            from apps.epg.tasks import buscar_caratulas
            buscar_caratulas.delay()
            messages.success(request, 'Buscando las carátulas que faltan con las fuentes nuevas. Tarda unos minutos.')
        return redirect('portal:settings')

    from apps.pvr.models import AjustesGrabacion

    if request.method == 'POST' and request.POST.get('accion') == 'grabaciones':
        ajustes = AjustesGrabacion.objects.filter(pk=1).first() or AjustesGrabacion()
        for campo in ('horas_por_cliente', 'horas_por_grabacion', 'meses_conservar', 'dias_aviso'):
            valor = request.POST.get(campo, '').strip()
            if valor.isdigit():
                setattr(ajustes, campo, min(int(valor), 9999))
        ajustes.save()
        messages.success(request, 'Ajustes de grabación guardados')
        return redirect('portal:settings')

    context = {
        'active_page': 'settings',
        'stats': get_base_stats(),
        'grabacion': AjustesGrabacion.objects.filter(pk=1).first() or AjustesGrabacion(),
        'fuentes': FuenteCaratula.objects.all(),
        'tmdb_env': bool(settings.QUATTRETV.get('TMDB_API_KEY')),
    }

    return render(request, 'portal/pages/settings.html', context)


# Novedades y ayuda
def _fecha_panel(texto):
    """Lo que manda un <input type="datetime-local">, en la hora del servidor."""
    from django.utils.dateparse import parse_datetime
    fecha = parse_datetime(texto or '')
    if fecha and timezone.is_naive(fecha):
        fecha = timezone.make_aware(fecha)
    return fecha


def _guardar_aviso(request, aviso):
    aviso.titulo = request.POST.get('titulo', '').strip()[:120]
    aviso.texto = request.POST.get('texto', '').strip()
    aviso.video_url = request.POST.get('video_url', '').strip()[:500]
    aviso.al_iniciar = 'al_iniciar' in request.POST
    aviso.en_ayuda = 'en_ayuda' in request.POST
    aviso.activo = 'activo' in request.POST
    aviso.desde = _fecha_panel(request.POST.get('desde'))
    aviso.hasta = _fecha_panel(request.POST.get('hasta'))
    veces = request.POST.get('veces', '')
    aviso.veces = int(veces) if veces.isdigit() else 3
    orden = request.POST.get('orden', '')
    aviso.orden = int(orden) if orden.lstrip('-').isdigit() else 0
    if request.FILES.get('video_archivo'):
        from django.core.files.storage import default_storage
        archivo = request.FILES['video_archivo']
        aviso.video_url = default_storage.save('ayuda/' + archivo.name, archivo)
    if request.FILES.get('imagen'):
        aviso.imagen = request.FILES['imagen']
    elif 'quitar_imagen' in request.POST:
        aviso.imagen = None
    aviso.save()


@staff_member_required
def ayuda_list(request):
    """Novedades que salen al arrancar y guias de la seccion Ayuda del portal."""
    from apps.devices.models import Aviso

    if request.method == 'POST':
        if not request.POST.get('titulo', '').strip():
            messages.error(request, 'Falta el título')
        else:
            aviso = Aviso()
            _guardar_aviso(request, aviso)
            messages.success(request, f'«{aviso.titulo}» guardado')
        return redirect('portal:ayuda')

    avisos = Aviso.objects.annotate(
        aparatos=Count('vistos'),
        no_quieren=Count('vistos', filter=Q(vistos__no_mostrar=True)),
    )
    context = {
        'active_page': 'ayuda',
        'stats': get_base_stats(),
        'avisos': avisos,
        'ahora': timezone.now(),
    }
    return render(request, 'portal/pages/ayuda.html', context)


@staff_member_required
def ayuda_edit(request, aviso_id):
    from apps.devices.models import Aviso

    aviso = get_object_or_404(Aviso, id=aviso_id)
    if request.method == 'POST':
        if not request.POST.get('titulo', '').strip():
            messages.error(request, 'Falta el título')
        else:
            _guardar_aviso(request, aviso)
            messages.success(request, f'«{aviso.titulo}» guardado')
            return redirect('portal:ayuda')
    context = {
        'active_page': 'ayuda',
        'stats': get_base_stats(),
        'aviso': aviso,
    }
    return render(request, 'portal/pages/ayuda_edit.html', context)


@staff_member_required
def ayuda_reset(request, aviso_id):
    """Que vuelva a salir en todos los aparatos, como si fuera nuevo."""
    from apps.devices.models import Aviso

    if request.method == 'POST':
        aviso = get_object_or_404(Aviso, id=aviso_id)
        aviso.vistos.all().delete()
        messages.success(request, f'«{aviso.titulo}» volverá a salir en todos los aparatos')
    return redirect('portal:ayuda')


@staff_member_required
def ayuda_delete(request, aviso_id):
    from apps.devices.models import Aviso

    if request.method == 'POST':
        aviso = get_object_or_404(Aviso, id=aviso_id)
        if aviso.imagen:
            aviso.imagen.delete(save=False)
        aviso.delete()
        messages.success(request, 'Borrado')
    return redirect('portal:ayuda')
