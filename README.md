# QuattreTV - IPTV Middleware

Middleware IPTV compatible con dispositivos STB MAG (Stalker Portal) con API moderna para aplicaciones multiplataforma.

## Características

- **Compatibilidad Stalker Portal**: Funciona con STB MAG existentes
- **API REST moderna**: Para apps iOS, Android, Smart TV, Web
- **Live TV**: Canales en vivo con categorías
- **EPG**: Guía de programación electrónica (XMLTV)
- **Timeshift/Catchup**: Reproducción de contenido pasado
- **PVR**: Grabaciones programadas
- **VOD**: Películas y series bajo demanda
- **Multi-dispositivo**: Control de dispositivos por usuario

## Requisitos

- Python 3.12+
- PostgreSQL 16+
- Redis 7+
- Docker y Docker Compose (opcional)

## Instalación Rápida (Docker)

```bash
# Clonar repositorio
git clone https://github.com/tu-usuario/quattretv.git
cd quattretv

# Copiar configuración
cp .env.example .env
# Editar .env con tus valores

# Iniciar servicios
docker-compose up -d

# Crear superusuario
docker-compose exec web python manage.py createsuperuser
```

## Instalación Manual

```bash
# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# o: venv\Scripts\activate  # Windows

# Instalar dependencias
pip install -r requirements.txt

# Configurar base de datos
cp .env.example .env
# Editar .env

# Migraciones
python manage.py migrate

# Crear superusuario
python manage.py createsuperuser

# Iniciar servidor
python manage.py runserver
```

## Estructura del Proyecto

```
quattretv/
├── config/              # Configuración Django
├── apps/
│   ├── core/           # Utilidades base
│   ├── accounts/       # Usuarios y suscripciones
│   ├── devices/        # Dispositivos STB
│   ├── channels/       # Canales y categorías
│   ├── epg/            # Guía de programación
│   ├── vod/            # Video bajo demanda
│   ├── timeshift/      # Timeshift/Catchup
│   ├── pvr/            # Grabaciones
│   └── stalker_api/    # API compatible Stalker
├── docker-compose.yml
└── requirements.txt
```

## Endpoints API

### API REST (v1)

| Endpoint | Descripción |
|----------|-------------|
| `/api/v1/accounts/` | Gestión de usuarios |
| `/api/v1/devices/` | Gestión de dispositivos |
| `/api/v1/channels/` | Canales y categorías |
| `/api/v1/epg/` | Guía de programación |
| `/api/v1/vod/` | Video on Demand |
| `/api/v1/timeshift/` | Timeshift/Catchup |
| `/api/v1/pvr/` | Grabaciones |

### API Stalker Portal

| Endpoint | Descripción |
|----------|-------------|
| `/portal.php` | Endpoint principal Stalker |
| `/stalker_portal/server/load.php` | Carga de portal |
| `/c/` | Alias corto |

## Configuración STB

Para conectar un STB MAG:

1. **Portal URL**: `http://tu-servidor/stalker_portal/c/`
2. Registrar MAC address en el panel admin
3. Asignar usuario y tarifa

## Panel de Administración

Acceder a `/admin/` con las credenciales de superusuario.

## Tareas Celery

```bash
# Worker
celery -A config worker -l info

# Beat (tareas programadas)
celery -A config beat -l info
```

## Desarrollo

```bash
# Tests
python manage.py test

# Lint
flake8 .

# Shell
python manage.py shell_plus
```

## Licencia

MIT License
