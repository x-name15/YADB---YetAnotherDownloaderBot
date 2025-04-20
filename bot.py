import discord
from discord.ext import commands
import yt_dlp
import os
import asyncio
import shutil
import time
import json
import redis
import re
import uuid
from datetime import datetime
import logging
import aiohttp
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure
from concurrent.futures import ThreadPoolExecutor
import subprocess
import sys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("DiscordBot")

BOT_PREFIX = os.getenv("BOT_PREFIX", "!")
BOT_NAME = os.getenv("BOT_NAME", "MediaDownloader")
BOT_VERSION = os.getenv("BOT_VERSION", "1.0.0")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=BOT_PREFIX, intents=intents)

RPC_ENABLED = os.getenv("RPC_ENABLED", "true").lower() == "true"
RPC_STATE = os.getenv("RPC_STATE", "Descargando contenido")
RPC_DETAILS = os.getenv("RPC_DETAILS", "Ayudando a usuarios")
RPC_LARGE_IMAGE = os.getenv("RPC_LARGE_IMAGE", "bot_logo")
RPC_LARGE_TEXT = os.getenv("RPC_LARGE_TEXT", "Bot de Descarga de Medios")
RPC_SMALL_IMAGE = os.getenv("RPC_SMALL_IMAGE", "discord_logo")
RPC_SMALL_TEXT = os.getenv("RPC_SMALL_TEXT", "Powered by Discord.py")
RPC_BUTTON_LABEL = os.getenv("RPC_BUTTON_LABEL", "Ver Repo")
RPC_BUTTON_URL = os.getenv("RPC_BUTTON_URL", "https://github.com/x-name15/YADB-YetAnotherDownloaderBot")

MONGODB_ENABLED = os.getenv("MONGODB_ENABLED", "false").lower() == "true"
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
MONGODB_DB = os.getenv("MONGODB_DB", "mediadownloader")
MONGODB_USER = os.getenv("MONGODB_USER", "")
MONGODB_PASSWORD = os.getenv("MONGODB_PASSWORD", "")
MONGODB_AUTH_SOURCE = os.getenv("MONGODB_AUTH_SOURCE", "admin")

timeout_str = os.getenv("DOWNLOAD_TIMEOUT", "600")
try:
    DOWNLOAD_TIMEOUT = int(timeout_str.split('#')[0].strip())
except ValueError:
    DOWNLOAD_TIMEOUT = 600
    logger.warning(f"Valor inválido para DOWNLOAD_TIMEOUT: '{timeout_str}', usando valor predeterminado: 600")

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))

DOWNLOAD_DIR = "./downloads"
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

download_queue = asyncio.Queue()

MAX_DOWNLOADS = int(os.getenv("MAX_DOWNLOADS", 4))

active_downloads = []

download_executor = ThreadPoolExecutor(max_workers=MAX_DOWNLOADS)

try:
    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)
    redis_client.ping()
    logger.info("Conexión a Redis establecida correctamente")
except redis.ConnectionError as e:
    logger.error(f"Error conectando a Redis: {e}")
    redis_client = None

mongo_client = None
db = None

async def setup_mongodb():
    global mongo_client, db

    if not MONGODB_ENABLED:
        logger.info("MongoDB está deshabilitado en la configuración. Usando almacenamiento JSON.")
        return
        
    try:

        logger.info(f"Intentando conectar a MongoDB: {MONGODB_URI}")

        mongo_client = AsyncIOMotorClient(
            MONGODB_URI,
            serverSelectionTimeoutMS=5000
        )

        await mongo_client.admin.command('ping')

        db = mongo_client[MONGODB_DB]
        logger.info(f"Conexión a MongoDB establecida correctamente. Base de datos: {MONGODB_DB}")

        if 'downloads' not in await db.list_collection_names():
            logger.info("Creando colección 'downloads'")

            await db.downloads.create_index("download_id", unique=True)
            await db.downloads.create_index("user_id")
            await db.downloads.create_index("status")
            
        logger.info("Configuración de MongoDB completada con éxito")
    except Exception as e:
        logger.error(f"Error configurando MongoDB: {e}")
        mongo_client = None
        db = None

async def save_download_record(record_data):
    try:

        if MONGODB_ENABLED and db is not None:
            logger.info(f"Guardando registro en MongoDB: {record_data.get('download_id')}")

            mongo_data = record_data.copy()

            if '_id' in mongo_data:
                del mongo_data['_id']

            download_id = mongo_data.get('download_id')

            if download_id:
                try:

                    result = await db.downloads.update_one(
                        {"download_id": download_id},
                        {"$set": mongo_data},
                        upsert=True
                    )
                    if result.upserted_id:
                        logger.info(f"Nuevo registro creado en MongoDB: {download_id}")
                    else:
                        logger.info(f"Registro actualizado en MongoDB: {download_id}")
                except Exception as mongo_error:
                    logger.error(f"Error al guardar en MongoDB: {mongo_error}")

                    await save_to_json(record_data)
            else:

                try:
                    result = await db.downloads.insert_one(mongo_data)
                    logger.info("Registro creado en MongoDB (sin download_id)")
                except Exception as mongo_error:
                    logger.error(f"Error al crear registro en MongoDB: {mongo_error}")

                    await save_to_json(record_data)
        else:

            logger.info("MongoDB deshabilitado, guardando en JSON")
            await save_to_json(record_data)
    except Exception as e:
        logger.error(f"Error al guardar registro de descarga: {e}")

        await save_to_json(record_data)

async def save_to_json(record_data):
    try:
        json_file = "download_records.json"
        logger.info(f"Intentando guardar en {json_file}")

        if os.path.exists(json_file):
            logger.info(f"El archivo {json_file} existe")

            logger.info(f"Permisos del archivo: {oct(os.stat(json_file).st_mode)}")
        else:
            logger.info(f"El archivo {json_file} no existe, creando...")
            with open(json_file, "w") as f:
                f.write("[]")

        records = []
        try:
            with open(json_file, "r") as f:
                content = f.read()
                logger.info(f"Contenido actual: {content[:100]}...")
                records = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Error al decodificar JSON: {e}")
            records = []
        except Exception as e:
            logger.error(f"Error al leer archivo JSON: {e}")
            records = []

        found = False
        for i, record in enumerate(records):
            if record.get('download_id') == record_data.get('download_id'):

                records[i] = record_data
                found = True
                break

        if not found:
            records.append(record_data)

        logger.info(f"Guardando {len(records)} registros en {json_file}")
        with open(json_file, "w") as f:
            json.dump(records, f, indent=2)
        
        logger.info(f"Registro guardado en JSON: {record_data.get('download_id', 'unknown')}")
    except Exception as e:
        logger.error(f"Error al guardar en JSON: {str(e)}")

class DownloadView(discord.ui.View):
    def __init__(self, url, info, ctx):
        super().__init__(timeout=None)
        self.url = url
        self.info = info
        self.ctx = ctx
        self.download_id = str(uuid.uuid4())

        self.is_playlist = 'entries' in info
        if self.is_playlist:
            self.playlist_size = len(info['entries'])
            self.title = info.get('title', 'Playlist')
        else:
            self.title = info.get('title', 'Desconocido')

        video_options = [
            ("Alta (720p+)", "720"),
            ("Media (480p)", "480"),
            ("Baja (360p-)", "360")
        ]
        
        for label, value in video_options:
            button = discord.ui.Button(label=label, style=discord.ButtonStyle.primary, custom_id=f"video_{value}")
            button.callback = self.video_button_callback
            self.add_item(button)

        audio_options = [
            ("Audio Alta", "high"),
            ("Audio Media", "medium"),
            ("Audio Baja", "low")
        ]
        
        for label, value in audio_options:
            button = discord.ui.Button(label=label, style=discord.ButtonStyle.success, custom_id=f"audio_{value}")
            button.callback = self.audio_button_callback
            self.add_item(button)

        if self.is_playlist:
            playlist_button = discord.ui.Button(
                label=f"Descargar Playlist ({self.playlist_size} videos)", 
                style=discord.ButtonStyle.danger, 
                custom_id="playlist"
            )
            playlist_button.callback = self.playlist_button_callback
            self.add_item(playlist_button)
    
    async def video_button_callback(self, interaction):
        quality = interaction.data["custom_id"].split("_")[1]
        await interaction.response.defer(ephemeral=True)

        if quality == "720":
            format_str = "bestvideo[height>=720]+bestaudio/best[height>=720]/best"
        elif quality == "480":
            format_str = "bestvideo[height>=480][height<720]+bestaudio/best[height>=480][height<720]/best"
        else:
            format_str = "bestvideo[height<480]+bestaudio/best[height<480]/best"
        
        await interaction.followup.send(f"Descarga de video en calidad {quality}p añadida a la cola.", ephemeral=True)
        await self.queue_download(format_str, "video", interaction, single=True)
    
    async def audio_button_callback(self, interaction):
        quality = interaction.data["custom_id"].split("_")[1]
        await interaction.response.defer(ephemeral=True)

        if quality == "high":
            format_str = "bestaudio/best"
        elif quality == "medium":
            format_str = "bestaudio[abr<=160]/best"
        else:
            format_str = "bestaudio[abr<=96]/best"
            
        await interaction.followup.send(f"Descarga de audio en calidad {quality} añadida a la cola.", ephemeral=True)
        await self.queue_download(format_str, "audio", interaction, single=True)
    
    async def playlist_button_callback(self, interaction):
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send(
            f"Añadiendo a la cola la playlist completa ({self.playlist_size} videos)...", 
            ephemeral=True
        )
        await self.queue_download("bestvideo[height>=480]+bestaudio/best", "video", interaction, single=False)
    
    async def queue_download(self, format_str, content_type, interaction, single=True):

        duration = None
        if not self.is_playlist and 'duration' in self.info:
            duration = self.info['duration']
        elif self.is_playlist and len(self.info['entries']) > 0:

            duration = 0
            for entry in self.info['entries']:
                if isinstance(entry, dict) and 'duration' in entry:
                    duration += entry.get('duration', 0)

        download_data = {
            'url': self.url,
            'format_str': format_str,
            'content_type': content_type,
            'user_id': interaction.user.id,
            'user_name': interaction.user.name,
            'channel_id': interaction.channel_id,
            'download_id': self.download_id,
            'timestamp': time.time(),
            'datetime': datetime.utcnow().isoformat(),
            'title': self.title,
            'duration': duration,
            'single': single,
            'is_playlist': self.is_playlist,
            'status': 'queued',
            'server_id': interaction.guild_id if interaction.guild else None
        }

        if redis_client:
            redis_key = f"download:{self.download_id}"
            redis_client.set(redis_key, json.dumps(download_data))
            redis_client.expire(redis_key, 86400)

        await save_download_record(download_data)

        await download_queue.put(download_data)

        embed = discord.Embed(
            title="📋 Descarga añadida a la cola",
            description=(
                f"{'Video' if content_type == 'video' else 'Audio'} "
                f"{'individual' if single else f'(playlist con {self.playlist_size} elementos)'} "
                f"añadido a la cola.\n\n"
                f"Posición actual: {download_queue.qsize()}\n"
                f"ID de descarga: `{self.download_id}`"
            ),
            color=discord.Color.blue()
        )

        embed.set_footer(text=f"{BOT_NAME} v{BOT_VERSION}", icon_url=bot.user.display_avatar.url if bot.user.display_avatar else None)
        embed.timestamp = datetime.utcnow()

        original_message = interaction.message
        await original_message.edit(view=None)

        await interaction.channel.send(
            content=f"<@{interaction.user.id}>",
            embed=embed
        )

async def download_worker():
    while True:

        if len(active_downloads) >= MAX_DOWNLOADS:
            await asyncio.sleep(5)
            continue

        try:
            download_data = await asyncio.wait_for(download_queue.get(), timeout=5.0)
        except asyncio.TimeoutError:
            await asyncio.sleep(1)
            continue

        active_downloads.append(download_data['download_id'])

        download_data['status'] = 'processing'
        await save_download_record(download_data)

        video_duration = download_data.get('duration', 0)
        if video_duration and isinstance(video_duration, (int, float)) and video_duration > 0:

            timeout = min(max(video_duration * 2, 120), 1800)
            logger.info(f"Timeout dinámico para descarga {download_data['download_id']}: {timeout} segundos (duración del video: {video_duration} segundos)")
        else:
            timeout = DOWNLOAD_TIMEOUT
            logger.info(f"Usando timeout predeterminado para descarga {download_data['download_id']}: {timeout} segundos")

        try:

            task = asyncio.create_task(process_download(download_data))
            await asyncio.wait_for(task, timeout=timeout)
        except asyncio.TimeoutError:

            logger.error(f"La descarga {download_data['download_id']} excedió el tiempo límite ({timeout} segundos)")

            channel = bot.get_channel(download_data['channel_id'])
            if channel:
                timeout_embed = discord.Embed(
                    title="⏱️ Tiempo de descarga excedido",
                    description=(
                        f"La descarga con ID `{download_data['download_id']}` fue cancelada porque excedió el tiempo límite de {timeout//60} minutos.\n"
                        f"Título: **{download_data.get('title', 'Desconocido')}**\n"
                        f"Esto suele ocurrir con videos muy largos o conexiones lentas."
                    ),
                    color=discord.Color.orange()
                )
                timeout_embed.set_footer(text=f"{BOT_NAME} v{BOT_VERSION}", icon_url=bot.user.display_avatar.url if bot.user.display_avatar else None)
                timeout_embed.timestamp = datetime.utcnow()
                
                await channel.send(content=f"<@{download_data['user_id']}>", embed=timeout_embed)

            download_data['status'] = 'error'
            download_data['error'] = f'Tiempo de descarga excedido ({timeout//60} minutos)'
            await save_download_record(download_data)

            try:
                download_path = f"{DOWNLOAD_DIR}/{download_data['download_id']}"
                if os.path.exists(download_path):
                    shutil.rmtree(download_path)
                if download_data['download_id'] in active_downloads:
                    active_downloads.remove(download_data['download_id'])
            except Exception as e:
                logger.error(f"Error al limpiar tras timeout: {str(e)}")

        download_queue.task_done()

async def process_download(download_data):
    try:

        url = download_data['url']
        format_str = download_data['format_str']
        content_type = download_data['content_type']
        user_id = download_data['user_id']
        channel_id = download_data['channel_id']
        download_id = download_data['download_id']
        single = download_data['single']
        title = download_data.get('title', 'Desconocido')

        is_spotify = re.search(r'(spotify\.com)', url) is not None

        download_path = f"{DOWNLOAD_DIR}/{download_id}"
        os.makedirs(download_path, exist_ok=True)

        channel = bot.get_channel(channel_id)
        if channel:
            start_embed = discord.Embed(
                title="⏱️ Descarga iniciada",
                description=(
                    f"La descarga con ID `{download_id}` ha comenzado a procesarse.\n"
                    f"Título: **{title}**\n"
                    f"Recibirás una notificación cuando esté lista."
                ),
                color=discord.Color.gold()
            )

            start_embed.set_footer(text=f"{BOT_NAME} v{BOT_VERSION}", icon_url=bot.user.display_avatar.url if bot.user.display_avatar else None)
            start_embed.timestamp = datetime.utcnow()
            
            await channel.send(content=f"<@{user_id}>", embed=start_embed)

        if is_spotify:
            return await process_spotify_download(download_data, download_path)

        ydl_opts = {
            'paths': {'home': download_path},
            'outtmpl': {'default': '%(title)s.%(ext)s'},
            'format': format_str,
            'quiet': True,
            'no_warnings': True,
            'socket_timeout': 60,
        }

        if re.search(r'(facebook\.com|fb\.com|fb\.watch)', url):

            ydl_opts['extract_flat'] = False
            
        elif re.search(r'(instagram\.com|instagr\.am)', url):

            ydl_opts['extract_flat'] = False
            
        elif re.search(r'(twitter\.com|x\.com)', url):

            ydl_opts['retries'] = 5

            if "best" in format_str and "+" in format_str:
                ydl_opts['format'] = 'best'

        if content_type == "audio":
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]

        if not single:
            ydl_opts['playlist_items'] = 'all'
        else:
            ydl_opts['noplaylist'] = True
        
        logger.info(f"Descargando con yt-dlp: {url}")

        def download_in_thread():
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
                return True, None
            except Exception as e:
                error_msg = str(e)

                if "is private" in error_msg or "This content is not available" in error_msg or "sign in" in error_msg:
                    return False, f"El contenido es privado o requiere inicio de sesión: {error_msg}"
                return False, error_msg

        success = False
        try:

            if not hasattr(bot, 'download_executor'):
                bot.download_executor = ThreadPoolExecutor(max_workers=MAX_DOWNLOADS)

            success, error = await bot.loop.run_in_executor(bot.download_executor, download_in_thread)
            
            if not success:
                logger.error(f"Error con yt-dlp: {error}")
                if channel:

                    if "privado" in error or "private" in error:
                        error_embed = discord.Embed(
                            title="🔒 Contenido privado o protegido",
                            description=(
                                f"No se pudo descargar este contenido porque está configurado como privado o protegido.\n\n"
                                f"Esto suele ocurrir con:\n"
                                f"• Cuentas privadas de Instagram/Facebook\n"
                                f"• Videos privados o restringidos\n"
                                f"• Contenido que requiere inicio de sesión\n\n"
                                f"Error: {error[:500]}"
                            ),
                            color=discord.Color.red()
                        )
                    else:
                        error_embed = discord.Embed(
                            title="❌ Error en la descarga",
                            description=f"No se pudo completar la descarga: {error[:1500]}",
                            color=discord.Color.red()
                        )
                    
                    error_embed.set_footer(text=f"{BOT_NAME} v{BOT_VERSION}", icon_url=bot.user.display_avatar.url if bot.user.display_avatar else None)
                    error_embed.timestamp = datetime.utcnow()
                    
                    await channel.send(content=f"<@{user_id}>", embed=error_embed)

                download_data['status'] = 'error'
                download_data['error'] = error[:500]
                await save_download_record(download_data)
                return
                
        except Exception as ydl_error:
            logger.error(f"Error con yt-dlp: {str(ydl_error)}")
            if channel:
                error_embed = discord.Embed(
                    title="❌ Error en la descarga",
                    description=f"No se pudo completar la descarga: {str(ydl_error)[:1500]}",
                    color=discord.Color.red()
                )
                error_embed.set_footer(text=f"{BOT_NAME} v{BOT_VERSION}", icon_url=bot.user.display_avatar.url if bot.user.display_avatar else None)
                error_embed.timestamp = datetime.utcnow()
                
                await channel.send(content=f"<@{user_id}>", embed=error_embed)

            download_data['status'] = 'error'
            download_data['error'] = str(ydl_error)[:500]
            await save_download_record(download_data)
            return
            
        if not success:
            return

        downloaded_files = []
        for root, _, files in os.walk(download_path):
            for file in files:
                if file.endswith(('.mp4', '.webm', '.mp3', '.ogg', '.m4a')):
                    file_path = os.path.join(root, file)
                    downloaded_files.append(file_path)

        if not downloaded_files:
            if channel:
                error_embed = discord.Embed(
                    title="❌ Error en la descarga",
                    description="No se encontraron archivos descargados.",
                    color=discord.Color.red()
                )
                error_embed.set_footer(text=f"{BOT_NAME} v{BOT_VERSION}", icon_url=bot.user.display_avatar.url if bot.user.display_avatar else None)
                error_embed.timestamp = datetime.utcnow()
                
                await channel.send(content=f"<@{user_id}>", embed=error_embed)

            download_data['status'] = 'error'
            download_data['error'] = 'No se encontraron archivos descargados'
            await save_download_record(download_data)
            return

        files_info = []

        for file_path in downloaded_files[:10]:
            file_size = os.path.getsize(file_path)
            file_name = os.path.basename(file_path)

            file_info = {
                'name': file_name,
                'size': file_size,
                'path': file_path,
                'compressed': False
            }

            if file_size > 25 * 1024 * 1024:
                compressed_path = f"{file_path}.zip"

                import zipfile
                with zipfile.ZipFile(compressed_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    zipf.write(file_path, arcname=os.path.basename(file_path))

                compressed_size = os.path.getsize(compressed_path)
                if os.path.exists(compressed_path) and compressed_size < 25 * 1024 * 1024:
                    file_path = compressed_path
                    file_name = os.path.basename(file_path)
                    is_compressed = True

                    file_info['compressed'] = True
                    file_info['compressed_size'] = compressed_size
                    file_info['compressed_path'] = compressed_path
                else:

                    if channel:
                        error_embed = discord.Embed(
                            title="⚠️ Archivo demasiado grande",
                            description=f"El archivo '{file_name}' es demasiado grande incluso comprimido ({file_size/(1024*1024):.2f} MB).",
                            color=discord.Color.orange()
                        )
                        error_embed.set_footer(text=f"{BOT_NAME} v{BOT_VERSION}", icon_url=bot.user.display_avatar.url if bot.user.display_avatar else None)
                        error_embed.timestamp = datetime.utcnow()
                        
                        await channel.send(content=f"<@{user_id}>", embed=error_embed)
                    continue
            else:
                is_compressed = False

            files_info.append(file_info)

            if channel:
                try:
                    success_embed = discord.Embed(
                        title="✅ Descarga Completada",
                        description=(
                            f"Archivo: **{file_name}**\n"
                            f"Tipo: {'Audio' if content_type == 'audio' else 'Video'}\n"
                            f"{'⚠️ *El archivo fue comprimido debido a su tamaño*' if is_compressed else ''}"
                        ),
                        color=discord.Color.green()
                    )

                    success_embed.set_footer(text=f"{BOT_NAME} v{BOT_VERSION}", icon_url=bot.user.display_avatar.url if bot.user.display_avatar else None)
                    success_embed.timestamp = datetime.utcnow()

                    await channel.send(
                        content=f"<@{user_id}>",
                        embed=success_embed,
                        file=discord.File(file_path, filename=file_name)
                    )
                except Exception as e:
                    logger.error(f"Error al enviar archivo: {str(e)}")
                    error_embed = discord.Embed(
                        title="❌ Error al enviar archivo",
                        description=f"No se pudo enviar el archivo: {str(e)}",
                        color=discord.Color.red()
                    )
                    error_embed.set_footer(text=f"{BOT_NAME} v{BOT_VERSION}", icon_url=bot.user.display_avatar.url if bot.user.display_avatar else None)
                    error_embed.timestamp = datetime.utcnow()
                    
                    await channel.send(content=f"<@{user_id}>", embed=error_embed)

        if len(downloaded_files) > 10:
            if channel:
                info_embed = discord.Embed(
                    title="ℹ️ Información",
                    description=f"Se descargaron {len(downloaded_files)} archivos, pero solo se enviaron los primeros 10 debido a limitaciones de Discord.",
                    color=discord.Color.blue()
                )
                info_embed.set_footer(text=f"{BOT_NAME} v{BOT_VERSION}", icon_url=bot.user.display_avatar.url if bot.user.display_avatar else None)
                info_embed.timestamp = datetime.utcnow()
                
                await channel.send(content=f"<@{user_id}>", embed=info_embed)

        download_data['status'] = 'completed'
        download_data['files'] = files_info
        download_data['completed_at'] = datetime.utcnow().isoformat()
        download_data['files_count'] = len(downloaded_files)
        download_data['files_sent'] = min(len(downloaded_files), 10)
        await save_download_record(download_data)
    
    except Exception as e:
        logger.error(f"Error en process_download: {str(e)}")
        channel = bot.get_channel(download_data['channel_id'])
        if channel:
            error_embed = discord.Embed(
                title="❌ Error inesperado",
                description=f"Ocurrió un error durante la descarga: {str(e)}",
                color=discord.Color.red()
            )
            error_embed.set_footer(text=f"{BOT_NAME} v{BOT_VERSION}", icon_url=bot.user.display_avatar.url if bot.user.display_avatar else None)
            error_embed.timestamp = datetime.utcnow()
            
            await channel.send(content=f"<@{download_data['user_id']}>", embed=error_embed)

        download_data['status'] = 'error'
        download_data['error'] = str(e)
        await save_download_record(download_data)
    
    finally:

        try:
            download_path = f"{DOWNLOAD_DIR}/{download_data['download_id']}"
            if os.path.exists(download_path):
                shutil.rmtree(download_path)
        except Exception as e:
            logger.error(f"Error al limpiar archivos: {str(e)}")

        try:
            if download_data['download_id'] in active_downloads:
                active_downloads.remove(download_data['download_id'])
        except:
            pass

async def process_spotify_download(download_data, download_path):
    """Procesa descargas de Spotify utilizando spotDL"""
    url = download_data['url']
    user_id = download_data['user_id']
    channel_id = download_data['channel_id']
    content_type = download_data['content_type']
    channel = bot.get_channel(channel_id)

    def check_spotdl_installed():
        try:
            subprocess.run(['spotdl', '--version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return True
        except (FileNotFoundError, subprocess.SubprocessError):
            return False

    is_spotdl_installed = await bot.loop.run_in_executor(None, check_spotdl_installed)
    
    if not is_spotdl_installed:
        if channel:
            error_embed = discord.Embed(
                title="❌ Error: spotDL no está instalado",
                description=(
                    "Para descargar contenido de Spotify, se requiere spotDL.\n\n"
                    "Por favor, contacta al administrador del bot para instalar spotDL."
                ),
                color=discord.Color.red()
            )
            error_embed.set_footer(text=f"{BOT_NAME} v{BOT_VERSION}", icon_url=bot.user.display_avatar.url if bot.user.display_avatar else None)
            error_embed.timestamp = datetime.utcnow()
            await channel.send(content=f"<@{user_id}>", embed=error_embed)

        download_data['status'] = 'error'
        download_data['error'] = 'spotDL no está instalado'
        await save_download_record(download_data)
        return

    spotify_type = "canción"
    if "album" in url:
        spotify_type = "álbum"
    elif "playlist" in url:
        spotify_type = "playlist"
    elif "show" in url or "episode" in url:
        spotify_type = "podcast"

    def run_spotdl():
        try:

            limit_arg = ["--limit", "10"] if "track" not in url else []

            cmd = ["spotdl", url, "--output", f"{download_path}/%(title)s.%(ext)s"] + limit_arg

            process = subprocess.run(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
            
            return True, process.stdout
        except subprocess.CalledProcessError as e:
            return False, f"Error de spotDL: {e.stderr}"
        except Exception as e:
            return False, f"Error: {str(e)}"

    if channel:
        info_embed = discord.Embed(
            title="🎵 Procesando Spotify",
            description=(
                f"Procesando {spotify_type} de Spotify con spotDL.\n\n"
                f"Esto tomará un momento mientras buscamos versiones equivalentes de las canciones."
            ),
            color=discord.Color.green()
        )
        info_embed.set_footer(text=f"{BOT_NAME} v{BOT_VERSION}", icon_url=bot.user.display_avatar.url if bot.user.display_avatar else None)
        info_embed.timestamp = datetime.utcnow()
        await channel.send(content=f"<@{user_id}>", embed=info_embed)

    success, result = await bot.loop.run_in_executor(None, run_spotdl)
    
    if not success:
        if channel:
            error_embed = discord.Embed(
                title="❌ Error al procesar Spotify",
                description=f"No se pudo descargar el contenido: {result}",
                color=discord.Color.red()
            )
            error_embed.set_footer(text=f"{BOT_NAME} v{BOT_VERSION}", icon_url=bot.user.display_avatar.url if bot.user.display_avatar else None)
            error_embed.timestamp = datetime.utcnow()
            await channel.send(content=f"<@{user_id}>", embed=error_embed)

        download_data['status'] = 'error'
        download_data['error'] = result[:500]
        await save_download_record(download_data)
        return

    downloaded_files = []
    for root, _, files in os.walk(download_path):
        for file in files:
            if file.endswith(('.mp3', '.ogg', '.m4a')):
                file_path = os.path.join(root, file)
                downloaded_files.append(file_path)

    if not downloaded_files:
        if channel:
            error_embed = discord.Embed(
                title="❌ No se encontraron canciones",
                description=(
                    "No se encontraron versiones equivalentes para este contenido de Spotify.\n\n"
                    "Esto puede ocurrir si:\n"
                    "• Las canciones son muy nuevas o poco conocidas\n"
                    "• El contenido no está disponible públicamente\n"
                    "• Hay restricciones regionales"
                ),
                color=discord.Color.red()
            )
            error_embed.set_footer(text=f"{BOT_NAME} v{BOT_VERSION}", icon_url=bot.user.display_avatar.url if bot.user.display_avatar else None)
            error_embed.timestamp = datetime.utcnow()
            await channel.send(content=f"<@{user_id}>", embed=error_embed)

        download_data['status'] = 'error'
        download_data['error'] = 'No se encontraron archivos equivalentes'
        await save_download_record(download_data)
        return

    files_info = []

    for file_path in downloaded_files[:10]:
        file_size = os.path.getsize(file_path)
        file_name = os.path.basename(file_path)

        file_info = {
            'name': file_name,
            'size': file_size,
            'path': file_path,
            'compressed': False,
            'source': 'spotify'
        }

        files_info.append(file_info)

        if channel:
            try:
                success_embed = discord.Embed(
                    title="✅ Descarga Spotify Completada",
                    description=f"Canción: **{file_name}**",
                    color=discord.Color.green()
                )

                success_embed.set_footer(text=f"{BOT_NAME} v{BOT_VERSION}", icon_url=bot.user.display_avatar.url if bot.user.display_avatar else None)
                success_embed.timestamp = datetime.utcnow()

                await channel.send(
                    content=f"<@{user_id}>",
                    embed=success_embed,
                    file=discord.File(file_path, filename=file_name)
                )
            except Exception as e:
                logger.error(f"Error al enviar archivo: {str(e)}")
                error_embed = discord.Embed(
                    title="❌ Error al enviar archivo",
                    description=f"No se pudo enviar el archivo: {str(e)}",
                    color=discord.Color.red()
                )
                error_embed.set_footer(text=f"{BOT_NAME} v{BOT_VERSION}", icon_url=bot.user.display_avatar.url if bot.user.display_avatar else None)
                error_embed.timestamp = datetime.utcnow()
                
                await channel.send(content=f"<@{user_id}>", embed=error_embed)

    if len(downloaded_files) > 10:
        if channel:
            info_embed = discord.Embed(
                title="ℹ️ Información",
                description=f"Se encontraron {len(downloaded_files)} canciones, pero solo se enviaron las primeras 10 debido a limitaciones de Discord.",
                color=discord.Color.blue()
            )
            info_embed.set_footer(text=f"{BOT_NAME} v{BOT_VERSION}", icon_url=bot.user.display_avatar.url if bot.user.display_avatar else None)
            info_embed.timestamp = datetime.utcnow()
            
            await channel.send(content=f"<@{user_id}>", embed=info_embed)

    download_data['status'] = 'completed'
    download_data['files'] = files_info
    download_data['completed_at'] = datetime.utcnow().isoformat()
    download_data['files_count'] = len(downloaded_files)
    download_data['files_sent'] = min(len(downloaded_files), 10)
    await save_download_record(download_data)

async def extract_with_platform_options(url, ctx):
    """Extrae información con opciones específicas para cada plataforma"""

    is_facebook = re.search(r'(facebook\.com|fb\.com|fb\.watch)', url) is not None
    is_instagram = re.search(r'(instagram\.com|instagr\.am)', url) is not None
    is_twitter = re.search(r'(twitter\.com|x\.com)', url) is not None
    is_spotify = re.search(r'(spotify\.com)', url) is not None

    processing_embed = discord.Embed(
        title="⏳ Procesando URL",
        description=f"Analizando contenido de {get_platform_name(url)}...",
        color=discord.Color.blue()
    )
    processing_embed.set_footer(text=f"{BOT_NAME} v{BOT_VERSION}", icon_url=bot.user.display_avatar.url if bot.user.display_avatar else None)
    processing_embed.timestamp = datetime.utcnow()
    
    processing_msg = await ctx.reply(embed=processing_embed)
    
    try:

        if is_spotify:

            def check_spotdl_installed():
                try:
                    subprocess.run(['spotdl', '--version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    return True
                except (FileNotFoundError, subprocess.SubprocessError):
                    return False

            is_spotdl_installed = await bot.loop.run_in_executor(None, check_spotdl_installed)
            
            if not is_spotdl_installed:
                await processing_msg.delete()
                error_embed = discord.Embed(
                    title="❌ Error: spotDL no está instalado",
                    description=(
                        "Para descargar contenido de Spotify, se requiere spotDL.\n\n"
                        "Por favor, contacta al administrador del bot para instalar spotDL."
                    ),
                    color=discord.Color.red()
                )
                error_embed.set_footer(text=f"{BOT_NAME} v{BOT_VERSION}", icon_url=bot.user.display_avatar.url if bot.user.display_avatar else None)
                error_embed.timestamp = datetime.utcnow()
                await ctx.reply(embed=error_embed)
                return None

            try:

                async with aiohttp.ClientSession() as session:
                    embed_url = f"https://open.spotify.com/oembed?url={url}"
                    async with session.get(embed_url) as response:
                        if response.status == 200:
                            spotify_data = await response.json()
                            title = spotify_data.get("title", "")

                            spotify_type = "canción"
                            if "album" in url:
                                spotify_type = "álbum"
                            elif "playlist" in url:
                                spotify_type = "playlist"
                            elif "show" in url or "episode" in url:
                                spotify_type = "podcast"

                            info = {
                                'title': title,
                                'extractor': 'spotify',
                                'url': url,
                                'spotify_type': spotify_type,
                                'thumbnail': spotify_data.get('thumbnail_url'),
                                'uploader': spotify_data.get('provider_name', 'Spotify')
                            }

                            if spotify_type in ["álbum", "playlist"]:
                                info['entries'] = [{'title': 'Múltiples canciones de Spotify'}]
                                
                            await processing_msg.delete()
                            return info
            except Exception as e:
                logger.error(f"Error al obtener metadatos de Spotify: {e}")

            await processing_msg.edit(
                embed=discord.Embed(
                    title="⏳ Procesando Spotify",
                    description="No se pudieron obtener metadatos de Spotify. Procesando como URL genérica...",
                    color=discord.Color.orange()
                )
            )

        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'socket_timeout': 30,
        }

        if is_facebook or is_instagram:

            ydl_opts['extract_flat'] = False
                
        elif is_twitter:

            ydl_opts['format'] = 'bestvideo+bestaudio/best'

            ydl_opts['retries'] = 5

        def extract_info():
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    return ydl.extract_info(url, download=False), None
            except Exception as e:
                error_msg = str(e)

                if any(x in error_msg.lower() for x in ["private", "privado", "not available", "sign in", "iniciar sesión"]):
                    return None, f"El contenido es privado o requiere inicio de sesión: {error_msg}"
                return None, error_msg

        loop = asyncio.get_event_loop()
        info, error = await loop.run_in_executor(None, extract_info)

        if error:
            await processing_msg.delete()

            if any(x in error.lower() for x in ["private", "privado", "not available", "sign in", "iniciar sesión"]):
                error_embed = discord.Embed(
                    title="🔒 Contenido privado o protegido",
                    description=(
                        f"No se puede acceder a este contenido porque es privado o requiere inicio de sesión.\n\n"
                        f"Esto suele ocurrir con:\n"
                        f"• Cuentas privadas de Instagram/Facebook\n"
                        f"• Videos privados o restringidos\n"
                        f"• Contenido que requiere inicio de sesión\n\n"
                        f"Error: {error[:500]}"
                    ),
                    color=discord.Color.red()
                )
            else:
                error_embed = discord.Embed(
                    title="❌ Error al procesar URL",
                    description=f"No se pudo extraer información: {error[:1500]}",
                    color=discord.Color.red()
                )
            
            error_embed.set_footer(text=f"{BOT_NAME} v{BOT_VERSION}", icon_url=bot.user.display_avatar.url if bot.user.display_avatar else None)
            error_embed.timestamp = datetime.utcnow()
            await ctx.reply(embed=error_embed)
            return None

        await processing_msg.delete()
        return info
        
    except Exception as e:

        await processing_msg.delete()
        raise e

def get_platform_name(url):
    """Obtiene el nombre de la plataforma basado en la URL"""
    if re.search(r'(facebook\.com|fb\.com|fb\.watch)', url):
        return "Facebook"
    elif re.search(r'(instagram\.com|instagr\.am)', url):
        return "Instagram"
    elif re.search(r'(twitter\.com|x\.com)', url):
        return "Twitter/X"
    elif re.search(r'(spotify\.com)', url):
        return "Spotify"
    elif re.search(r'(youtube\.com|youtu\.be)', url):
        return "YouTube"
    elif re.search(r'(tiktok\.com)', url):
        return "TikTok"
    else:
        return "la plataforma"

async def setup_rich_presence():
    if not RPC_ENABLED:
        return
    
    try:

        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name=RPC_STATE,
            details=RPC_DETAILS,
        )

        await bot.change_presence(activity=activity)
        logger.info("Rich Presence configurado correctamente")
    except Exception as e:
        logger.error(f"Error al configurar Rich Presence: {e}")

@bot.command()
async def download(ctx, url: str):

    if not url.startswith(('http://', 'https://')):
        embed = discord.Embed(
            title="❌ URL Inválida",
            description="Por favor proporciona una URL válida.",
            color=discord.Color.red()
        )
        embed.set_footer(text=f"{BOT_NAME} v{BOT_VERSION}", icon_url=bot.user.display_avatar.url if bot.user.display_avatar else None)
        embed.timestamp = datetime.utcnow()
        
        await ctx.reply(embed=embed)
        return
    
    try:

        info = await extract_with_platform_options(url, ctx)

        if not info:
            return

        is_playlist = 'entries' in info
        
        if is_playlist:
            playlist_title = info.get('title', 'Playlist')
            playlist_count = len(info['entries'])

            embed = discord.Embed(
                title=f"📋 {get_platform_name(url)}: Playlist detectada",
                description=(
                    f"**{playlist_title}**\n"
                    f"Contiene **{playlist_count}** videos/audios\n\n"
                    f"Selecciona una opción para descargar:"
                ),
                color=discord.Color.blue()
            )

            if 'thumbnail' in info:
                embed.set_thumbnail(url=info['thumbnail'])

            embed.set_footer(text=f"{BOT_NAME} v{BOT_VERSION}", icon_url=bot.user.display_avatar.url if bot.user.display_avatar else None)
            embed.timestamp = datetime.utcnow()

            view = DownloadView(url, info, ctx)
            await ctx.send(embed=embed, view=view)
            
        else:

            title = info.get('title', 'Desconocido')
            duration = info.get('duration')
            if duration:
                try:
                    minutes = int(duration) // 60
                    seconds = int(duration) % 60
                    duration_str = f"{minutes}:{seconds:02d}"
                except (TypeError, ValueError):
                    duration_str = f"{duration}"
                else:
                    duration_str = "Desconocido"
            thumbnail = info.get('thumbnail')
            uploader = info.get('uploader', 'Desconocido')

            if info.get('extractor') == 'spotify':
                embed = discord.Embed(
                    title=f"🎵 Spotify: {info.get('spotify_type', 'Contenido')}",
                    description=(
                        f"**{title}**\n"
                        f"Plataforma: Spotify\n\n"
                        f"**Selecciona una opción de descarga:**\n"
                        f"(Se buscará una versión equivalente en YouTube)"
                    ),
                    color=discord.Color.green()
                )
            else:
                embed = discord.Embed(
                    title=f"📥 {get_platform_name(url)}: Descargar Contenido",
                    description=(
                        f"**{title}**\n"
                        f"Subido por: {uploader}\n"
                        f"Duración: {duration_str}\n\n"
                        f"**Selecciona una opción de descarga:**"
                    ),
                    color=discord.Color.blue()
                )
            
            if thumbnail:
                embed.set_thumbnail(url=thumbnail)

            embed.set_footer(text=f"{BOT_NAME} v{BOT_VERSION}", icon_url=bot.user.display_avatar.url if bot.user.display_avatar else None)

            embed.set_footer(text=f"{BOT_NAME} v{BOT_VERSION}", icon_url=bot.user.display_avatar.url if bot.user.display_avatar else None)
            embed.timestamp = datetime.utcnow()

            view = DownloadView(url, info, ctx)
            await ctx.send(embed=embed, view=view)
    
    except Exception as e:
        error_embed = discord.Embed(
            title="❌ Error al procesar URL",
            description=f"No se pudo procesar la URL: {str(e)}",
            color=discord.Color.red()
        )
        error_embed.set_footer(text=f"{BOT_NAME} v{BOT_VERSION}", icon_url=bot.user.display_avatar.url if bot.user.display_avatar else None)
        error_embed.timestamp = datetime.utcnow()
        
        await ctx.reply(embed=error_embed)

@bot.command()
async def queue(ctx):
    """Muestra el estado actual de la cola de descargas"""

    queue_size = download_queue.qsize()

    active_count = len(active_downloads)
    
    embed = discord.Embed(
        title="📋 Estado de la Cola de Descargas",
        description=(
            f"**Descargas en cola:** {queue_size}\n"
            f"**Descargas activas:** {active_count}/{MAX_DOWNLOADS}\n\n"
            f"El tiempo de espera dependerá del tamaño y cantidad de archivos en la cola."
        ),
        color=discord.Color.blue()
    )
    embed.set_footer(text=f"{BOT_NAME} v{BOT_VERSION}", icon_url=bot.user.display_avatar.url if bot.user.display_avatar else None)
    embed.timestamp = datetime.utcnow()
    
    await ctx.reply(embed=embed)

@bot.command()
async def stats(ctx):
    """Muestra estadísticas de las descargas realizadas"""
    try:
        stats_data = {}

        if MONGODB_ENABLED and db is not None:
            try:
                total_downloads = await db.downloads.count_documents({})
                completed = await db.downloads.count_documents({"status": "completed"})
                errors = await db.downloads.count_documents({"status": "error"})
                in_progress = await db.downloads.count_documents({"status": {"$in": ["queued", "processing"]}})

                pipeline = [
                    {"$group": {"_id": "$user_id", "count": {"$sum": 1}, "name": {"$first": "$user_name"}}},
                    {"$sort": {"count": -1}},
                    {"$limit": 5}
                ]
                top_users = await db.downloads.aggregate(pipeline).to_list(length=5)
                
                stats_data = {
                    "total": total_downloads,
                    "completed": completed,
                    "errors": errors,
                    "in_progress": in_progress,
                    "top_users": top_users
                }
                logger.info("Estadísticas obtenidas desde MongoDB")
            except Exception as mongo_err:
                logger.error(f"Error al obtener estadísticas de MongoDB: {mongo_err}")

                stats_data = get_stats_from_json()
        else:

            stats_data = get_stats_from_json()

        embed = discord.Embed(
            title="📊 Estadísticas de Descargas",
            description=(
                f"**Total de descargas:** {stats_data.get('total', 0)}\n"
                f"**Completadas:** {stats_data.get('completed', 0)}\n"
                f"**Errores:** {stats_data.get('errors', 0)}\n"
                f"**En progreso:** {stats_data.get('in_progress', 0)}"
            ),
            color=discord.Color.blue()
        )

        if stats_data.get('top_users'):
            top_users_text = "\n".join([
                f"{idx+1}. {user.get('name', 'Usuario')} - {user.get('count', 0)} descargas"
                for idx, user in enumerate(stats_data.get('top_users', []))
            ])
            embed.add_field(name="👑 Usuarios más activos", value=top_users_text or "No hay datos")

        storage_type = "MongoDB" if MONGODB_ENABLED and db is not None else "JSON local"
        embed.add_field(name="💾 Almacenamiento", value=storage_type, inline=False)
        
        embed.set_footer(text=f"{BOT_NAME} v{BOT_VERSION}", icon_url=bot.user.display_avatar.url if bot.user.display_avatar else None)
        embed.timestamp = datetime.utcnow()
        
        await ctx.reply(embed=embed)
    
    except Exception as e:
        logger.error(f"Error al obtener estadísticas: {e}")
        error_embed = discord.Embed(
            title="❌ Error",
            description=f"No se pudieron obtener las estadísticas: {str(e)}",
            color=discord.Color.red()
        )
        error_embed.set_footer(text=f"{BOT_NAME} v{BOT_VERSION}", icon_url=bot.user.display_avatar.url if bot.user.display_avatar else None)
        error_embed.timestamp = datetime.utcnow()
        
        await ctx.reply(embed=error_embed)

def get_stats_from_json():
    try:
        json_file = "download_records.json"
        if os.path.exists(json_file):
            with open(json_file, "r") as f:
                try:
                    records = json.load(f)

                    total_downloads = len(records)
                    completed = sum(1 for r in records if r.get("status") == "completed")
                    errors = sum(1 for r in records if r.get("status") == "error")
                    in_progress = sum(1 for r in records if r.get("status") in ["queued", "processing"])

                    user_counts = {}
                    for record in records:
                        user_id = record.get("user_id")
                        user_name = record.get("user_name", "Usuario")
                        if user_id:
                            if user_id not in user_counts:
                                user_counts[user_id] = {"count": 0, "name": user_name}
                            user_counts[user_id]["count"] += 1

                    top_users = [{"_id": uid, "count": data["count"], "name": data["name"]} 
                                for uid, data in sorted(user_counts.items(), key=lambda x: x[1]["count"], reverse=True)[:5]]
                    
                    return {
                        "total": total_downloads,
                        "completed": completed,
                        "errors": errors,
                        "in_progress": in_progress,
                        "top_users": top_users
                    }
                except json.JSONDecodeError:
                    return {
                        "total": 0, "completed": 0, "errors": 0, "in_progress": 0, "top_users": []
                    }
        else:
            return {
                "total": 0, "completed": 0, "errors": 0, "in_progress": 0, "top_users": []
            }
    except Exception as e:
        logger.error(f"Error al obtener estadísticas de JSON: {e}")
        return {
            "total": 0, "completed": 0, "errors": 0, "in_progress": 0, "top_users": []
        }

@bot.event
async def on_ready():
    logger.info(f"Bot iniciado como {bot.user}")

    await setup_mongodb()

    await setup_rich_presence()

    bot.loop.create_task(download_worker())

    try:
        for item in os.listdir(DOWNLOAD_DIR):
            item_path = os.path.join(DOWNLOAD_DIR, item)
            if os.path.isdir(item_path):
                shutil.rmtree(item_path)
    except Exception as e:
        logger.error(f"Error al limpiar directorio de descargas: {str(e)}")

bot.run(os.getenv("DISCORD_TOKEN"))
