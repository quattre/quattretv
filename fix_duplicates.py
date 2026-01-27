#!/usr/bin/env python
"""
Script para eliminar canales duplicados.
Mantiene el canal con el ID más bajo y elimina los duplicados.
"""
import os
import sys

# Mock celery before importing anything else
class MockCelery:
    def __init__(self, *args, **kwargs):
        pass
    def config_from_object(self, *args, **kwargs):
        pass
    def autodiscover_tasks(self, *args, **kwargs):
        pass

celery_module = type(sys)('celery')
celery_module.Celery = MockCelery
sys.modules['celery'] = celery_module

import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, '/home/sergio/quattretv')

django.setup()

from django.db.models import Count
from apps.channels.models import Channel

def fix_duplicates():
    # Encontrar nombres duplicados
    duplicates = (
        Channel.objects.values('name')
        .annotate(count=Count('id'))
        .filter(count__gt=1)
    )

    print(f"Encontrados {len(duplicates)} nombres con duplicados")

    total_deleted = 0
    for dup in duplicates:
        name = dup['name']
        # Obtener todos los canales con este nombre, ordenados por ID (mantener el más antiguo)
        channels = Channel.objects.filter(name=name).order_by('id')

        # Mantener el primero, eliminar el resto
        first = channels.first()
        to_delete = channels.exclude(id=first.id)

        count = to_delete.count()
        if count > 0:
            print(f"  - '{name}': manteniendo #{first.number} (id={first.id}), eliminando {count} duplicados")
            to_delete.delete()
            total_deleted += count

    # También buscar por número de canal duplicado
    dup_numbers = (
        Channel.objects.values('number')
        .annotate(count=Count('id'))
        .filter(count__gt=1)
    )

    print(f"\nEncontrados {len(dup_numbers)} números con duplicados")

    for dup in dup_numbers:
        number = dup['number']
        channels = Channel.objects.filter(number=number).order_by('id')

        first = channels.first()
        to_delete = channels.exclude(id=first.id)

        count = to_delete.count()
        if count > 0:
            print(f"  - Número {number}: manteniendo '{first.name}' (id={first.id}), eliminando {count} duplicados")
            to_delete.delete()
            total_deleted += count

    print(f"\n✓ Total eliminados: {total_deleted} canales duplicados")
    print(f"✓ Canales restantes: {Channel.objects.count()}")

if __name__ == '__main__':
    fix_duplicates()
