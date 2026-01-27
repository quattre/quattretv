#!/usr/bin/env python
"""
Script para arreglar canales: marcar radios y renumerar.
"""
import os
import sys

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, '/home/sergio/quattretv')
django.setup()

from apps.channels.models import Channel

def fix_channels():
    # 1. Marcar como radio los que tienen "radio" en nombre o URL
    radio_keywords = ['radio_', '/radio/', 'radio clasica', 'rne', 'kiss fm', 'hit fm',
                      'onda cero', 'europa fm', 'melodia fm', 'cope', 'marca', 'vaughan',
                      'cadena 100', 'radio maria', 'es radio', 'cadena ser', 'los 40',
                      'cadena dial', '97.7 la radio', '97laradio']

    all_channels = Channel.objects.all()
    radios_marked = 0

    for ch in all_channels:
        name_lower = ch.name.lower()
        url_lower = (ch.stream_url or '').lower()

        is_radio = False
        for keyword in radio_keywords:
            if keyword in name_lower or keyword in url_lower:
                is_radio = True
                break

        if is_radio and not ch.is_radio:
            ch.is_radio = True
            ch.save()
            radios_marked += 1
            print(f"  Radio: {ch.name}")

    print(f"\n✓ Marcados {radios_marked} canales como radio")

    # 2. Renumerar TV (solo los que NO son radio)
    tv_channels = Channel.objects.filter(is_radio=False, is_active=True).order_by('number')
    print(f"\n--- Renumerando {tv_channels.count()} canales de TV ---")

    num = 1
    for ch in tv_channels:
        if ch.number != num:
            print(f"  TV {ch.name}: {ch.number} -> {num}")
            ch.number = num
            ch.save()
        num += 1

    # 3. Renumerar Radio (solo los que SÍ son radio)
    radio_channels = Channel.objects.filter(is_radio=True, is_active=True).order_by('number')
    print(f"\n--- Renumerando {radio_channels.count()} emisoras de radio ---")

    num = 1
    for ch in radio_channels:
        # Para radio usamos números altos (1000+) para evitar conflictos
        new_num = 1000 + num
        if ch.number != new_num:
            print(f"  Radio {ch.name}: {ch.number} -> {new_num}")
            ch.number = new_num
            ch.save()
        num += 1

    # Resumen
    print(f"\n=== RESUMEN ===")
    print(f"Total TV: {Channel.objects.filter(is_radio=False).count()}")
    print(f"Total Radio: {Channel.objects.filter(is_radio=True).count()}")

if __name__ == '__main__':
    fix_channels()
