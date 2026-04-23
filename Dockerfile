# Используем официальный образ Python как базу приложения
FROM python:3.13.5-bookworm

WORKDIR /app

# Системные пакеты нужны для сборки psycopg2 и работы мультимедиа-зависимостей
RUN if [ -f /etc/apt/sources.list ]; then sed -i 's/deb.debian.org/mirror.yandex.ru/g' /etc/apt/sources.list; fi && \
    find /etc/apt/sources.list.d -type f -name '*.sources' -exec sed -i 's/deb.debian.org/mirror.yandex.ru/g' {} + && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
        ffmpeg \
        libsm6 \
        libxext6 && \
    rm -rf /var/lib/apt/lists/*

# Сначала копируем только зависимости, чтобы pip install кэшировался при правках кода
COPY requirements.txt .

RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Код копируется последним: изменения в .py файлах не сбрасывают слой с зависимостями
COPY . .

CMD ["python", "main.py"]
