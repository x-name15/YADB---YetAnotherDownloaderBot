YADB-YetAnotherDownloaderBot
===================

Un bot de Discord potente y versátil para descargar contenido multimedia de múltiples plataformas, incluyendo YouTube, TikTok, Twitter, Instagram, Facebook y Spotify.

🌟 Características
------------------

*   **Múltiples Plataformas**: Descarga de YouTube, TikTok, Twitter/X, Instagram, Facebook y Spotify
    
*   **Diferentes Formatos**: Descargas en formato video o audio con opciones de calidad
    
*   **Soporte para Playlists**: Descarga listas de reproducción completas
    
*   **Cola de Descargas**: Sistema de cola para gestionar múltiples solicitudes
    
*   **Base de Datos**: Almacenamiento de historial de descargas en MongoDB o JSON
    
*   **Timeout Dinámico**: Ajusta el tiempo de espera según la duración del contenido
    
*   **Compresión Automática**: Comprime archivos grandes para cumplir con los límites de Discord
    
*   **Interfaz Intuitiva**: Botones para seleccionar opciones de descarga
    
*   **Estadísticas**: Seguimiento de descargas y usuarios más activos
    

📋 Comandos
-----------

*   !download \[URL\] - Descarga contenido de la URL proporcionada
    
*   !queue - Muestra el estado actual de la cola de descargas
    
*   !stats - Muestra estadísticas sobre las descargas realizadas
    

🔧 Requisitos
-------------

*   Python 3.8+
    
*   Docker y Docker Compose (recomendado)
    
*   Token de bot de Discord
    
*   Conexión a Internet
    
*   spotDL (opcional, para descargas de Spotify)
    

🚀 Instalación
--------------

### Usando Docker (Recomendado)

1.  bashgit clone https://github.com/usuario/media-downloader.gitcd media-downloader
    
2.  CodeDISCORD\_TOKEN=tu\_token\_aquíBOT\_PREFIX=!BOT\_NAME=MediaDownloaderBOT\_VERSION=1.0.0MONGODB\_ENABLED=trueMONGODB\_DB=mediadownloaderMAX\_DOWNLOADS=4DOWNLOAD\_TIMEOUT=600
    
3.  bashdocker-compose up -d
    

### Instalación Manual

1.  bashgit clone https://github.com/usuario/media-downloader.gitcd media-downloader
    
2.  bashpip install -r requirements.txtpip install spotdl # Opcional, para soporte de Spotify
    
3.  Crea un archivo .env con las variables necesarias.
    
4.  bashpython bot.py
    

⚙️ Configuración
----------------

Todas las configuraciones se realizan a través de variables de entorno en el archivo .env:

**VariableDescripciónValor Predeterminado**DISCORD\_TOKENToken del bot de Discord_Requerido_BOT\_PREFIXPrefijo para comandos!BOT\_NAMENombre del botMediaDownloaderBOT\_VERSIONVersión del bot1.0.0MONGODB\_ENABLEDActivar MongoDBtrueMONGODB\_URIURI de MongoDBmongodb://mongo:27017/MONGODB\_DBBase de datos de MongoDBmediadownloaderMAX\_DOWNLOADSDescargas simultáneas máximas4DOWNLOAD\_TIMEOUTTiempo de espera en segundos600RPC\_ENABLEDActivar Rich Presencetrue

⚠️ Solución de Problemas
------------------------

*   **Error con Spotify**: Asegúrate de tener spotDL instalado (pip install spotdl).
    
*   **Problemas con Redis/MongoDB**: Verifica que los contenedores estén en ejecución (docker-compose ps).
    
*   **Descargas Fallidas**: Algunas plataformas pueden limitar las descargas. Asegúrate de que el contenido sea público.
    
*   **El Bot No Responde**: Verifica los logs (docker-compose logs -f discord-bot).
    

📝 Notas
--------

*   Este bot está diseñado para uso personal y educativo.
    
*   Respeta los términos de servicio de las plataformas.
    
*   No está diseñado para descargar contenido con derechos de autor sin permiso.
    

📄 Licencia
-----------

Este proyecto está licenciado bajo la Licencia MIT. Consulta el archivo LICENSE para más detalles.

🙏 Créditos
-----------

*   [discord.py](https://github.com/Rapptz/discord.py)
    
*   [yt-dlp](https://github.com/yt-dlp/yt-dlp)
    
*   [spotDL](https://github.com/spotDL/spotify-downloader)
    
*   [MongoDB](https://www.mongodb.com/)
    
*   [Redis](https://redis.io/)
