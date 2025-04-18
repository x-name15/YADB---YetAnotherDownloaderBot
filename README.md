# MediaDownloader Bot

Un bot de Discord potente y versátil para descargar contenido multimedia de múltiples plataformas, incluyendo YouTube, TikTok, Twitter, Instagram, Facebook y Spotify.

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![Discord.py](https://img.shields.io/badge/discord.py-2.0+-blueviolet)

## 🌟 Características

- **Múltiples Plataformas**: Descarga de YouTube, TikTok, Twitter/X, Instagram, Facebook y Spotify
- **Diferentes Formatos**: Descargas en formato video o audio con opciones de calidad
- **Soporte para Playlists**: Descarga listas de reproducción completas
- **Cola de Descargas**: Sistema de cola para gestionar múltiples solicitudes
- **Base de Datos**: Almacenamiento de historial de descargas en MongoDB o JSON
- **Timeout Dinámico**: Ajusta el tiempo de espera según la duración del contenido
- **Compresión Automática**: Comprime archivos grandes para cumplir con los límites de Discord
- **Interfaz Intuitiva**: Botones para seleccionar opciones de descarga
- **Estadísticas**: Seguimiento de descargas y usuarios más activos

## 📋 Comandos

- `!download [URL]` - Descarga contenido de la URL proporcionada
- `!queue` - Muestra el estado actual de la cola de descargas
- `!stats` - Muestra estadísticas sobre las descargas realizadas

## 🔧 Requisitos

- Python 3.8+
- Docker y Docker Compose (recomendado)
- Token de bot de Discord
- Conexión a Internet
- spotDL (opcional, para descargas de Spotify)

## 🚀 Instalación

### Usando Docker (Recomendado)

1. Clona el repositorio:
   ```bash
   git clone https://github.com/usuario/media-downloader.git
   cd media-downloader
