FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install system dependencies: FFmpeg (with built-in x264/x265 support),
# libass for subtitle burning, fonts, and build tools for C-extension pip
# packages (tgcrypto needs a compiler + Python headers)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libass9 \
    fontconfig \
    fonts-freefont-ttf \
    git \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python packages (separate layer for caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy bot source files
COPY . .

# Run the bot
CMD ["python", "bot.py"]
