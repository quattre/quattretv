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

- Python 3.10+
- PostgreSQL 14+
- Redis 6+ (opcional, para Celery)

---

## Instalación del Backend

### Opción A: Con Docker (Recomendado)

```bash
# 1. Clonar repositorio
git clone https://github.com/quattre/quattretv.git
cd quattretv

# 2. Copiar configuración
cp .env.example .env

# 3. Iniciar todos los servicios
docker compose up -d

# 4. Ejecutar migraciones
docker compose exec web python manage.py migrate

# 5. Crear usuario administrador
docker compose exec web python manage.py createsuperuser
```

**Servicios que se inician:**
- `web`: Django en puerto 8000
- `db`: PostgreSQL en puerto 5432
- `redis`: Redis en puerto 6379
- `celery`: Worker para tareas asíncronas
- `celery-beat`: Tareas programadas (EPG updates)

### Opción B: Instalación Manual (Sin Docker)

#### 1. Instalar dependencias del sistema

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3.10-venv python3-pip postgresql postgresql-contrib redis-server -y

# Iniciar servicios
sudo systemctl start postgresql
sudo systemctl start redis-server
```

#### 2. Crear base de datos PostgreSQL

```bash
# Acceder a PostgreSQL
sudo -u postgres psql

# En la consola de PostgreSQL:
CREATE DATABASE quattretv;
CREATE USER quattretv WITH PASSWORD 'quattretv';
GRANT ALL PRIVILEGES ON DATABASE quattretv TO quattretv;
ALTER USER quattretv CREATEDB;
\q
```

#### 3. Configurar el proyecto

```bash
# Clonar repositorio
git clone https://github.com/quattre/quattretv.git
cd quattretv

# Crear entorno virtual
python3 -m venv venv
source venv/bin/activate

# Instalar dependencias Python
pip install -r requirements.txt

# Copiar y editar configuración
cp .env.example .env
nano .env  # Editar con tus valores
```

#### 4. Configurar .env

Edita el archivo `.env` con estos valores:

```env
# Django
SECRET_KEY=genera-una-clave-secreta-aqui
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1,tu-ip-local

# Base de datos
DATABASE_URL=postgres://quattretv:quattretv@localhost:5432/quattretv

# Redis (para Celery)
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1

# Servidor de streaming (tu servidor de streams)
STREAMING_SERVER_URL=http://localhost:8080
TIMESHIFT_ENABLED=True
TIMESHIFT_HOURS=24

# CORS (permitir conexiones desde apps)
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8080
```

#### 5. Ejecutar migraciones y crear admin

```bash
# Activar entorno virtual (si no está activo)
source venv/bin/activate

# Ejecutar migraciones
python manage.py migrate

# Crear superusuario administrador
python manage.py createsuperuser
# Ingresa: usuario, email, contraseña
```

#### 6. Iniciar el servidor

```bash
# Desarrollo (un solo comando)
python manage.py runserver 0.0.0.0:8000

# O para producción con Gunicorn:
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 4
```

#### 7. Iniciar Celery (opcional, para tareas asíncronas)

```bash
# En otra terminal, activar venv y ejecutar:
source venv/bin/activate

# Worker para procesar tareas
celery -A config worker -l info

# Beat para tareas programadas (en otra terminal)
celery -A config beat -l info
```

---

## URLs del Backend

| URL | Descripción |
|-----|-------------|
| http://localhost:8000/admin/ | Panel de administración Django |
| http://localhost:8000/api/v1/ | API REST para apps |
| http://localhost:8000/portal.php | API Stalker Portal para STB |

---

## Configuración de Dispositivos STB (MAG)

### Conectar un decodificador MAG/STB:

1. En el STB, ir a **Settings > Servers > Portal**
2. Configurar **Portal URL**: `http://TU-IP:8000/stalker_portal/c/`
3. Anotar la **MAC Address** del dispositivo

### Registrar el dispositivo en el panel:

1. Acceder a http://localhost:8000/admin/
2. Ir a **Devices > Devices > Add**
3. Ingresar:
   - MAC Address: `00:1A:79:XX:XX:XX`
   - Usuario asignado
   - Tarifa/Plan
4. Guardar

El STB debería conectarse automáticamente.

---

## API REST Endpoints

### Autenticación
```
POST /api/v1/accounts/login/     # Login (JWT)
POST /api/v1/accounts/register/  # Registro
POST /api/v1/accounts/refresh/   # Refresh token
```

### Canales
```
GET  /api/v1/channels/                    # Lista de canales
GET  /api/v1/channels/{id}/               # Detalle canal
GET  /api/v1/channels/categories/         # Categorías
GET  /api/v1/channels/{id}/stream/        # URL de streaming
```

### EPG (Guía de programación)
```
GET  /api/v1/epg/                         # Programación actual
GET  /api/v1/epg/channel/{id}/            # EPG de un canal
GET  /api/v1/epg/now/                     # Programas en emisión
```

### VOD (Video on Demand)
```
GET  /api/v1/vod/movies/                  # Películas
GET  /api/v1/vod/series/                  # Series
GET  /api/v1/vod/movies/{id}/             # Detalle película
```

### Timeshift/Catchup
```
GET  /api/v1/timeshift/                   # Archivos disponibles
GET  /api/v1/timeshift/{channel_id}/      # Catchup de un canal
```

### PVR (Grabaciones)
```
GET  /api/v1/pvr/recordings/              # Mis grabaciones
POST /api/v1/pvr/recordings/              # Programar grabación
DELETE /api/v1/pvr/recordings/{id}/       # Eliminar grabación
```

---

## App Flutter

La app Flutter está en el directorio `app_flutter/`.

### Requisitos
- Flutter 3.16+
- Dart 3.2+

### Instalación

```bash
cd app_flutter

# Instalar dependencias
flutter pub get
```

### Configurar servidor

Edita `lib/core/constants/api_constants.dart`:

```dart
class ApiConstants {
  // Cambiar por la IP de tu servidor
  static const String baseUrl = 'http://192.168.1.100:8000';
  // ...
}
```

### Ejecutar en diferentes plataformas

```bash
# Android (móvil)
flutter run

# Android TV
flutter run -d <android-tv-device-id>

# iOS (requiere macOS)
cd ios && pod install && cd ..
flutter run -d iPhone

# Web
flutter run -d chrome
```

### Compilar para producción

```bash
# Android APK
flutter build apk --release

# Android App Bundle (Play Store)
flutter build appbundle --release

# iOS (requiere macOS y cuenta de desarrollador)
flutter build ios --release
```

---

## Estructura del Proyecto

```
quattretv/
├── config/                  # Configuración Django
│   ├── settings.py         # Settings principal
│   ├── urls.py             # URLs raíz
│   ├── celery.py           # Configuración Celery
│   └── wsgi.py             # WSGI para producción
├── apps/
│   ├── accounts/           # Usuarios, tarifas, sesiones
│   ├── devices/            # Dispositivos STB/MAG
│   ├── channels/           # Canales y categorías
│   ├── epg/                # Guía de programación
│   ├── vod/                # Películas y series
│   ├── timeshift/          # Timeshift/Catchup
│   ├── pvr/                # Grabaciones DVR
│   └── stalker_api/        # API compatible Stalker Portal
├── app_flutter/            # App multiplataforma
│   ├── lib/
│   │   ├── core/           # API client, theme, router
│   │   └── features/       # Pantallas y providers
│   ├── android/            # Config Android/Android TV
│   └── ios/                # Config iOS
├── docker-compose.yml      # Servicios Docker
├── requirements.txt        # Dependencias Python
├── Dockerfile              # Imagen Docker
└── nginx.conf              # Config Nginx
```

---

## Desarrollo

### Ejecutar tests
```bash
python manage.py test
```

### Crear migraciones
```bash
python manage.py makemigrations
python manage.py migrate
```

### Shell interactivo
```bash
python manage.py shell
```

### Cargar datos de ejemplo
```bash
python manage.py loaddata fixtures/sample_data.json
```

---

## Troubleshooting

### Error: "Connection refused" al conectar la app
- Verifica que el servidor esté corriendo en `0.0.0.0:8000`
- Asegúrate que el firewall permita el puerto 8000
- En la app, usa la IP de tu máquina, no `localhost`

### Error: "CORS policy" en la app
- Añade tu IP/dominio en `CORS_ALLOWED_ORIGINS` en `.env`
- Reinicia el servidor

### STB no conecta
- Verifica la MAC address en el panel admin
- Comprueba que el dispositivo tenga tarifa asignada
- URL del portal: `http://IP:8000/stalker_portal/c/`

### Error de base de datos
```bash
# Verificar que PostgreSQL esté corriendo
sudo systemctl status postgresql

# Recrear base de datos
sudo -u postgres dropdb quattretv
sudo -u postgres createdb quattretv
python manage.py migrate
```

---

## Licencia

MIT License
