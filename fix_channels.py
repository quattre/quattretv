#!/usr/bin/env python
"""
Script para arreglar canales: marcar radios y renumerar correlativamente.
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
    radio_keywords = ['radio_', '/radio/', 'radio clasica', 'rne 3', 'rne exterior',
                      'kiss fm', 'hit fm', 'onda cero', 'europa fm', 'melodia fm',
                      'cope', 'cadena 100', 'radio maria', 'es radio', 'cadena ser',
                      'los 40', 'cadena dial', '97.7 la radio', '97laradio', 'vaughan',
                      'marca']

    all_channels = Channel.objects.all()
    radios_marked = 0

    print("=== PASO 1: Detectando radios ===")
    for ch in all_channels:
        name_lower = ch.name.lower()
        url_lower = (ch.stream_url or '').lower()

        is_radio = False
        for keyword in radio_keywords:
            if keyword in name_lower or keyword in url_lower:
                is_radio = True
                break

        if is_radio != ch.is_radio:
            ch.is_radio = is_radio
            ch.save()
            if is_radio:
                radios_marked += 1
                print(f"  + Radio: {ch.name}")

    print(f"\n✓ Marcados {radios_marked} canales como radio")

    # 2. Renumerar TV correlativamente (1, 2, 3...)
    # Primero ponemos números temporales altos para evitar conflictos de unique
    tv_channels = list(Channel.objects.filter(is_radio=False, is_active=True).order_by('id'))
    print(f"\n=== PASO 2: Renumerando {len(tv_channels)} canales de TV ===")

    # Números temporales
    for i, ch in enumerate(tv_channels):
        ch.number = 90000 + i
        ch.save()

    # Números finales
    for i, ch in enumerate(tv_channels):
        new_num = i + 1
        print(f"  TV #{new_num}: {ch.name}")
        ch.number = new_num
        ch.save()

    # 3. Renumerar Radio correlativamente (1, 2, 3...)
    radio_channels = list(Channel.objects.filter(is_radio=True, is_active=True).order_by('id'))
    print(f"\n=== PASO 3: Renumerando {len(radio_channels)} emisoras de radio ===")

    # Números temporales
    for i, ch in enumerate(radio_channels):
        ch.number = 80000 + i
        ch.save()

    # Números finales (empezando en 1)
    for i, ch in enumerate(radio_channels):
        new_num = i + 1
        print(f"  Radio #{new_num}: {ch.name}")
        ch.number = new_num
        ch.save()

    # Resumen
    print(f"\n{'='*40}")
    print(f"=== RESUMEN ===")
    print(f"Total TV: {Channel.objects.filter(is_radio=False).count()} canales (numerados 1 a {len(tv_channels)})")
    print(f"Total Radio: {Channel.objects.filter(is_radio=True).count()} emisoras (numeradas 1 a {len(radio_channels)})")
    print(f"{'='*40}")

if __name__ == '__main__':
    fix_channels()
