# Emilia — многофункциональный Discord-бот

Emilia — русскоязычный Discord-бот на Python и [disnake](https://docs.disnake.dev/) для администрирования и повседневной жизни сервера. Бот собирает статистику активности, воспроизводит музыку, проводит конкурсы и розыгрыши, принимает заявки, публикует анонимные сообщения, конвертирует видео и включает мини-игру «Алхимия» с генерацией новых элементов через GigaChat.

## Возможности

- профили участников и рейтинги по сообщениям, голосовой активности и времени на сервере;
- музыка с YouTube, персональные очереди и управление воспроизведением;
- мини-игра «Алхимия» с валютой, ежедневной наградой, инвентарём и общими рецептами;
- конкурсы постов по реакциям и розыгрыши со случайным выбором победителей;
- настраиваемые панели набора с формами заявок;
- анонимные публикации с изображениями, PDF- и TXT-файлами;
- конвертация видео в MOV или GIF через slash-команду и контекстное меню;
- суточная статистика сообщений по выбранным каналам;
- закрытые служебные команды владельца: роли, логи, серверы, каналы и выгрузка истории;
- раздельные пользовательские и технические логи с ежедневной ротацией.

## Стек

- Python 3.11+;
- disnake 2.12.1;
- PostgreSQL 15 и SQLAlchemy;
- GigaChat API;
- yt-dlp, FFmpeg, PyNaCl и dave.py для музыки;
- MoviePy и imageio-ffmpeg для конвертации видео;
- APScheduler для ежедневных задач;
- Docker и Docker Compose для развёртывания.

## Архитектура

```mermaid
flowchart TD
    Discord[Discord API] --> Main[main.py<br/>события и запуск]
    Main --> Cogs[app/modules/cogs<br/>команды]
    Cogs --> UI[menus и modals<br/>интерактивные формы]
    Cogs --> DB[database.py<br/>операции с данными]
    Main --> Messages[messages.py<br/>статистика и конкурсы]
    Main --> Scripts[scripts.py<br/>видео и фоновые задачи]
    Cogs --> Music[yt-dlp + FFmpeg]
    Cogs --> Alchemy[alchemy_service.py<br/>GigaChat]
    DB --> Models[alchemy_connect.py<br/>SQLAlchemy-модели]
    Models --> PostgreSQL[(PostgreSQL)]
    Main --> Logs[logger.py<br/>UTF-8 логи]
```

Основные части проекта:

```text
.
├── main.py                         # запуск бота, события Discord, планировщик
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── app/modules/
    ├── alchemy_connect.py          # подключение к PostgreSQL и ORM-модели
    ├── alchemy_service.py          # генерация и проверка результатов алхимии
    ├── database.py                 # слой доступа к данным
    ├── logger.py                   # ежедневные info/technical логи
    ├── messages.py                 # обработка сообщений и статистика
    ├── scripts.py                  # конкурсы, конвертация и задачи по расписанию
    ├── cogs/                       # slash-, prefix- и context-menu команды
    ├── menus/                      # кнопки и выпадающие меню
    └── modals/                     # формы розыгрышей, набора и анонимных сообщений
```

Коги загружаются автоматически из `app/modules/cogs`. Таблицы создаются через `Base.metadata.create_all()` при старте приложения; несколько изменений существующей схемы выполняются встроенной функцией обновления.

## Команды

Полная интерактивная справка доступна прямо в Discord через `/help` и `/help_command`.

| Раздел | Команды |
|---|---|
| Справка и утилиты | `/help`, `/help_command`, `/ping`, `/profile`, `/leaderboard`, `/avatar`, `/banner`, `/server_info` |
| Алхимия | `/alchemy_start`, `/daily`, `/balance`, `/alchemy_combine`, `/alchemy_inventory`, `/alchemy_recipes` |
| Музыка | `/play`, `/skip`, `/stop`, `/pause`, `/resume`, `/queue`, `/leave` |
| Публикации и файлы | `/convert`, `/anonimuska`, контекстные команды `Convert Video` и `Convert Video to GIF` |
| Администрирование | `/role`, `/contest`, `/add_statistic`, `/recruitment_create`, `/giveaway_create`, `/add_anonimus_channel` |


## Требования к Discord-приложению

1. Создайте приложение и бота в [Discord Developer Portal](https://discord.com/developers/applications).
2. Включите привилегированные intents: `Server Members Intent`, `Presence Intent` и `Message Content Intent`. Приложение создаёт бота с `Intents.all()`.
3. Пригласите бота со scope `bot applications.commands`.
4. Выдайте права, необходимые используемым функциям: просмотр каналов, отправка сообщений, embeds и файлов, история сообщений, реакции, управление сообщениями и ролями, а также подключение и голосовая передача.

В коде ссылка приглашения использует право `Administrator`. Для рабочего сервера безопаснее сформировать собственную ссылку с минимальным набором разрешений.

## Настройка окружения

Создайте в корне файл `.env`. Не добавляйте его в Git.

```dotenv
# Discord
DISCORD_MAIN_TOKEN=your_discord_bot_token

# PostgreSQL: используется приложением при локальном запуске
DATABASE_URL=postgresql://emilia:change_me@localhost:5432/emilia

# PostgreSQL: используются docker-compose.yml
POSTGRES_USER=emilia
POSTGRES_PASSWORD=change_me
POSTGRES_DB=emilia

# GigaChat для генерации новых элементов алхимии
GIGACHAT_API_KEY=your_gigachat_credentials
GIGACHAT_MODEL=GigaChat
GIGACHAT_VERIFY_SSL_CERTS=false
GIGACHAT_MAX_CONCURRENT_REQUESTS=1
GIGACHAT_GENERATION_ATTEMPTS=5

# Экономика алхимии
ALCHEMY_START_BALANCE=50
DAILY_REWARD=25
ALCHEMY_COMBINE_COST=5

# Необязательные настройки
DEBUG_LOGS=false
LOGS_DIR=app/modules/logs
# FFMPEG_PATH=C:\\ffmpeg\\bin\\ffmpeg.exe
```

### Переменные окружения

| Переменная | Обязательна | Значение по умолчанию | Назначение |
|---|---:|---|---|
| `DISCORD_MAIN_TOKEN` | да | — | токен Discord-бота |
| `DATABASE_URL` | да | — | строка подключения SQLAlchemy к PostgreSQL |
| `GIGACHAT_API_KEY` | для новых рецептов | — | credentials GigaChat API |
| `GIGACHAT_MODEL` | нет | `GigaChat` | модель генерации |
| `GIGACHAT_VERIFY_SSL_CERTS` | нет | `false` | проверка SSL-сертификата GigaChat |
| `GIGACHAT_MAX_CONCURRENT_REQUESTS` | нет | `1` | число одновременных запросов генерации |
| `GIGACHAT_GENERATION_ATTEMPTS` | нет | `5` | максимум попыток получить допустимый новый элемент |
| `ALCHEMY_START_BALANCE` | нет | `50` | стартовый баланс игрока |
| `DAILY_REWARD` | нет | `25` | ежедневная награда; поддерживается старое имя `ALCHEMY_DAILY_REWARD` |
| `ALCHEMY_COMBINE_COST` | нет | `5` | стоимость одного сочетания |
| `FFMPEG_PATH` | нет | автоопределение | явный путь к исполняемому файлу FFmpeg |
| `LOGS_DIR` | нет | `app/modules/logs` | каталог ежедневных логов |
| `DEBUG_LOGS` | нет | `false` | запись debug-сообщений в технический лог |

`DISCORD_TEST_TOKEN` читается в `main.py`, но в текущей версии не используется для запуска.

## Локальный запуск

Потребуются запущенный PostgreSQL и установленный FFmpeg.

### Windows PowerShell

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main.py
```

### Linux/macOS

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main.py
```

При старте приложение до пяти раз проверяет доступность PostgreSQL с интервалом пять секунд, создаёт недостающие таблицы, загружает коги и синхронизирует команды Discord.

## Запуск через Docker Compose

После заполнения `.env`:

```bash
docker compose up -d --build
docker compose logs -f emilia-bot
```

Остановка контейнеров:

```bash
docker compose down
```

Данные PostgreSQL сохраняются в именованном томе `pg_data`, а логи бота — в локальном каталоге `./logs`.

> [!WARNING]
> В текущем `docker-compose.yml` токен передаётся контейнеру как `DISCORD_TOKEN`, тогда как приложение читает `DISCORD_MAIN_TOKEN`. Кроме того, `.dockerignore` пока не исключает `.env`, поэтому файл с секретами может попасть в образ. Перед production-развёртыванием исправьте имя переменной на `DISCORD_MAIN_TOKEN: ${DISCORD_MAIN_TOKEN}` и добавьте `.env` в `.dockerignore`.

## Особенности подсистем

### Музыка

- принимает ссылку на видео, ссылку на плейлист или поисковый запрос YouTube;
- сохраняет персональные очереди в PostgreSQL;
- ограничивает очередь 200 треками и показывает по 15 треков на странице;
- автоматически отключается, когда в голосовом канале не остаётся слушателей;
- использует системный FFmpeg, `FFMPEG_PATH` или бинарник из `imageio-ffmpeg`.

### Алхимия

- выдаёт четыре стартовых элемента: вода, огонь, земля и воздух;
- хранит глобальные рецепты и открытия конкретного сервера;
- проверяет наличие исходных элементов и списывает валюту до генерации;
- возвращает валюту при ошибке GigaChat;
- принимает только русские названия длиной до трёх слов и отбрасывает дубликаты и нежелательные однокоренные результаты.

### Статистика

- счётчики сообщений пользователей записываются в БД пакетами раз в 30 секунд;
- голосовые сессии учитываются по событиям входа, выхода и перехода между каналами;
- для отдельно отслеживаемых каналов ежедневная сводка отправляется в `00:00` по локальному времени процесса.

### Видео и GIF

- одновременно обрабатывается до пяти задач;
- MOV создаётся с H.264/AAC;
- GIF ограничивается шириной 480 px и частотой до 12 FPS;
- видео длиннее 10 секунд ускоряется, чтобы GIF уложился в лимит;
- временные файлы удаляются после завершения задачи.

### Логи

Логи записываются в UTF-8 и разделяются на:

- `info_YYYY-MM-DD.log` — пользовательские действия и штатные события;
- `technical_YYYY-MM-DD.log` — предупреждения, ошибки и debug-события.

Файлы старше 30 дней удаляются автоматически.

## Разработка

Быстрая проверка синтаксиса всех Python-модулей:

```bash
python -m compileall main.py app
```