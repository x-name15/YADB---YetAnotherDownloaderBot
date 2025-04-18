FROM python:3.10-slim
WORKDIR /app
RUN apt-get update && apt-get install -y \
    ffmpeg \ 
    curl \
    unzip \
    zip \
    build-essential \
    libffi-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir --upgrade yt-dlp
RUN yt-dlp --version
COPY bot.py bot.py
RUN mkdir -p /app/downloads && chmod 777 /app/downloads
RUN echo "[]" > /app/download_records.json && chmod 666 /app/download_records.json
CMD ["python", "bot.py"]