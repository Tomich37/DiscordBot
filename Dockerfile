# Используем официальный образ Python
FROM python:3.11.3

# Устанавливаем зависимости из файла requirements.txt
COPY requirements.txt /app/
WORKDIR /app
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код бота в контейнер
COPY . /app

# Команда для запуска бота
CMD ["python", "main.py"]