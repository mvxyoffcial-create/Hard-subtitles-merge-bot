FROM python:3.10-slim

# Install system dependencies, FFmpeg, and encoders for both x264 and x265
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libx264-dev \
    libx265-dev \
    libass-dev \
    fontconfig \
    fonts-freefont-ttf \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy bot source files
COPY . .

# Run the bot
CMD ["python", "bot.py"]
