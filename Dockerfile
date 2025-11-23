# Используем официальный образ Python
FROM python:3.13.5-bookworm as builder

# Устанавливаем системные зависимости для psycopg2
RUN sed -i 's/deb.debian.org/mirror.yandex.ru/g' /etc/apt/sources.list && \
    apt-get update && \
    apt-get install -y \
        libpq-dev \
        gcc \
        ffmpeg \
        libsm6 \
        curl \
        libxext6 && \
    rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://deno.land/install.sh | sh

FROM python:3.13.5-bookworm
WORKDIR /app
COPY . .

RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

CMD ["python", "main.py"]