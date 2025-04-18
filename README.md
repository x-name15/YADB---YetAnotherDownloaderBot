# YADB - Yet Another Downloader Bot

YADB (Yet Another Downloader Bot) is a powerful and versatile Discord bot designed to download multimedia content from multiple platforms, including YouTube, TikTok, Twitter, Instagram, Facebook, and Spotify.

[![Version](https://img.shields.io/badge/version-1.0.0-blue)](https://github.com/x-name15/YADB---YetAnotherDownloaderBot)
[![Discord.py](https://img.shields.io/badge/discord.py-2.0+-blueviolet)](https://discordpy.readthedocs.io/)

## 🌟 Features

- **Multi-Platform Support**: Download from YouTube, TikTok, Twitter/X, Instagram, Facebook, and Spotify.
- **Audio & Video Options**: Download in both video and audio formats with quality options.
- **Playlist Support**: Download entire playlists with ease.
- **Download Queue**: Manage multiple requests through a queue system.
- **Database Integration**: Store download history in MongoDB or fallback to JSON.
- **Dynamic Timeout**: Automatically adjusts the timeout based on content duration.
- **File Compression**: Compresses large files to comply with Discord upload limits.
- **Interactive Interface**: Use Discord buttons to choose download options.
- **Statistics**: Track downloads and display the most active users.

## 📋 Commands

- `!download [URL]` - Download content from the provided URL.
- `!queue` - Show the current status of the download queue.
- `!stats` - Display statistics about downloads and usage.

## 🔧 Requirements

- Python 3.8+
- Docker and Docker Compose (recommended)
- Discord bot token
- Internet connection
- spotDL (optional, for Spotify downloads)

## 🚀 Installation

### Using Docker (Recommended)

1. Clone the repository:
   ```bash
   git clone https://github.com/x-name15/YADB-YetAnotherDownloaderBot.git
   cd YADB-YetAnotherDownloaderBot
   ```

2. Create a `.env` file with the necessary variables:
   ```
   DISCORD_TOKEN=your_discord_token_here
   BOT_PREFIX=!
   BOT_NAME=YADB-YetAnotherDownloaderBot
   BOT_VERSION=1.0.0
   MONGODB_ENABLED=true
   MONGODB_DB=yadb
   MAX_DOWNLOADS=4
   DOWNLOAD_TIMEOUT=600
   ```

3. Start the containers:
   ```bash
   docker-compose up -d
   ```

### Manual Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/x-name15/YADB---YetAnotherDownloaderBot.git
   cd YADB---YetAnotherDownloaderBot
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   pip install spotdl  # Optional, for Spotify support
   ```

3. Create a `.env` file with the necessary variables.

4. Start the bot:
   ```bash
   python bot.py
   ```

## ⚙️ Configuration

All configurations are done through environment variables in the `.env` file:

| Variable         | Description                       | Default Value                  |
|------------------|-----------------------------------|--------------------------------|
| DISCORD_TOKEN    | Discord bot token                | *Required*                    |
| BOT_PREFIX       | Command prefix                   | !                              |
| BOT_NAME         | Name of the bot                  | YADB-YetAnotherDownloaderBot  |
| BOT_VERSION      | Version of the bot               | 1.0.0                         |
| MONGODB_ENABLED  | Enable MongoDB                   | true                          |
| MONGODB_URI      | URI for MongoDB                  | mongodb://mongo:27017/        |
| MONGODB_DB       | MongoDB database name            | yadb                          |
| MAX_DOWNLOADS    | Maximum simultaneous downloads   | 4                              |
| DOWNLOAD_TIMEOUT | Timeout in seconds               | 600                            |
| RPC_ENABLED      | Enable Rich Presence             | true                           |

## ⚠️ Troubleshooting

- **Error with Spotify**: Ensure `spotDL` is installed (`pip install spotdl`).
- **Issues with Redis/MongoDB**: Verify that the containers are running (`docker-compose ps`).
- **Failed Downloads**: Some platforms restrict downloads. Ensure the content is public.
- **Bot Not Responding**: Check the logs (`docker-compose logs -f discord-bot`).

## 📝 Notes

- This bot is designed for personal and educational use.
- Please respect the terms of service of the platforms.
- This bot is not intended to download copyrighted content without permission.

## 📄 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## 🙏 Credits

- [discord.py](https://github.com/Rapptz/discord.py)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- [spotDL](https://github.com/spotDL/spotify-downloader)
- [MongoDB](https://www.mongodb.com/)
- [Redis](https://redis.io/)
