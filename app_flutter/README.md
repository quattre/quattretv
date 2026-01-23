# QuattreTV - Flutter App

Aplicación multiplataforma para el middleware QuattreTV IPTV.

## Plataformas Soportadas

- Android (móvil y TV)
- iOS
- Android TV
- Fire TV
- Web (experimental)

## Características

- **TV en Vivo**: Lista de canales con logos y EPG actual
- **Guía de Programación (EPG)**: Programación completa con catchup
- **Video On Demand**: Películas y series
- **Timeshift/Catchup**: Reproducción de contenido pasado
- **Grabaciones (PVR)**: Gestión de grabaciones
- **Control Parental**: PIN para contenido adulto
- **Multi-perfil**: Soporte para múltiples dispositivos

## Requisitos

- Flutter 3.16+
- Dart 3.2+

## Instalación

```bash
# Clonar repositorio
cd quattretv/app_flutter

# Instalar dependencias
flutter pub get

# Generar código (modelos, providers)
flutter pub run build_runner build --delete-conflicting-outputs

# Ejecutar en desarrollo
flutter run
```

## Configuración

Edita `lib/core/constants/api_constants.dart` para configurar la URL del servidor:

```dart
class ApiConstants {
  static const String baseUrl = 'http://tu-servidor:8000';
  // ...
}
```

## Estructura del Proyecto

```
lib/
├── main.dart                    # Entry point
├── core/
│   ├── api/                     # API client y modelos
│   │   ├── api_client.dart
│   │   └── models/
│   ├── config/                  # Tema y rutas
│   │   ├── app_theme.dart
│   │   └── app_router.dart
│   ├── constants/               # Constantes
│   └── widgets/                 # Widgets reutilizables
└── features/
    ├── auth/                    # Login y autenticación
    │   ├── providers/
    │   └── presentation/
    ├── channels/                # TV en vivo
    │   ├── providers/
    │   └── presentation/
    ├── epg/                     # Guía de programación
    │   ├── providers/
    │   └── presentation/
    ├── home/                    # Navegación principal
    ├── player/                  # Reproductor de video
    ├── pvr/                     # Grabaciones
    ├── settings/                # Ajustes
    ├── splash/                  # Pantalla de carga
    └── vod/                     # Video on demand
        ├── providers/
        └── presentation/
```

## Compilar para Producción

### Android
```bash
flutter build apk --release
# o para App Bundle
flutter build appbundle --release
```

### iOS

#### Requisitos para iOS
- macOS con Xcode 14.0+
- Cuenta de desarrollador de Apple (para dispositivo físico)
- CocoaPods instalado (`sudo gem install cocoapods`)

#### Configuración inicial
```bash
# Navegar al directorio iOS
cd ios

# Instalar dependencias de CocoaPods
pod install

# Volver al directorio principal
cd ..
```

#### Ejecutar en simulador
```bash
# Listar simuladores disponibles
flutter devices

# Ejecutar en simulador iPhone
flutter run -d "iPhone 15 Pro"
```

#### Ejecutar en dispositivo físico
1. Abre `ios/Runner.xcworkspace` en Xcode
2. Selecciona tu equipo de desarrollo en Signing & Capabilities
3. Conecta tu iPhone y selecciónalo como destino
4. Ejecuta con `flutter run` o desde Xcode

#### Compilar para producción
```bash
# Build para release
flutter build ios --release

# Para subir a App Store:
# 1. Abre ios/Runner.xcworkspace en Xcode
# 2. Product > Archive
# 3. Distribute App > App Store Connect
```

#### Solución de problemas iOS
- **CocoaPods error**: Ejecuta `cd ios && pod repo update && pod install`
- **Signing error**: Verifica tu cuenta de desarrollador en Xcode
- **Build failed**: Ejecuta `flutter clean && flutter pub get && cd ios && pod install`

### Android TV
```bash
# El mismo APK funciona en Android TV
# Asegúrate de tener configurado el manifiesto para TV
flutter build apk --release
```

### Web
```bash
flutter build web --release
```

## Dependencias Principales

| Paquete | Uso |
|---------|-----|
| flutter_riverpod | Estado y providers |
| dio | Cliente HTTP |
| go_router | Navegación |
| video_player | Reproductor de video |
| chewie | Controles de video |
| hive | Almacenamiento local |
| cached_network_image | Cache de imágenes |

## Personalización

### Tema
Edita `lib/core/config/app_theme.dart` para personalizar colores y estilos.

### Logo
Reemplaza los archivos en `assets/images/` y `assets/icons/`.

## TV Remote Support

La app soporta navegación con control remoto en Android TV:
- D-pad para navegación
- Enter para seleccionar
- Back para volver

## Licencia

MIT License
