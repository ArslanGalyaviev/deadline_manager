# Deadline Manager API

Асинхронный REST API сервис для управления личными дедлайнами и задачами с системой уведомлений.

## Возможности

- **Полный CRUD**: создание, чтение, обновление и удаление задач.
- **Фильтрация на уровне БД**: динамическая фильтрация дедлайнов по категории и приоритету через query-параметры.
- **Асинхронные фоновые задачи**: отправка email-уведомлений о новых дедлайнах через SMTP без блокировки HTTP-ответа (`asyncio.create_task`).
- **Управление схемой БД**: использование Alembic для версионирования и применения миграций.
- **Контейнеризация**: полная изоляция приложения и PostgreSQL через Docker Compose с настройкой `healthcheck`.
- **Интеграционное тестирование**: изолированные тесты API с использованием in-memory SQLite и `httpx.ASGITransport`.

## Технологии

- **Язык**: Python 3.12+
- **Фреймворк**: FastAPI, Pydantic V2
- **База данных**: PostgreSQL 15 (основная), SQLite (для тестов)
- **ORM и миграции**: SQLAlchemy 2.0 (async), asyncpg, Alembic
- **Фоновые задачи**: aiosmtplib, asyncio
- **Инфраструктура**: Docker, Docker Compose
- **Тестирование**: pytest, pytest-asyncio, httpx

## Архитектура

```text
deadline_manager/
├── alembic/                 # Скрипты миграций Alembic
│   ├── versions/            # Файлы сгенерированных миграций
│   └── env.py               # Конфигурация асинхронного окружения Alembic
├── tests/                   # Интеграционные тесты API
│   ├── __init__.py
│   └── test_api.py          # Тесты CRUD-операций и обработки ошибок (404)
├── .gitignore
├── alembic.ini              # Основной конфиг Alembic
├── docker-compose.yml       # Оркестрация сервисов (PostgreSQL + Web с healthcheck)
├── Dockerfile               # Образ приложения (slim, non-root user)
├── main.py                  # Точка входа: модели SQLAlchemy, Pydantic-схемы, роуты FastAPI
├── pytest.ini               # Конфигурация pytest (asyncio_mode = auto)
└── requirements.txt         # Зависимости проекта

## Тестирование

pytest tests/ -v

## Как это работает

1. При старте через Docker Compose инициализируется контейнер PostgreSQL. Веб-сервис ждет его готовности благодаря depends_on: condition: service_healthy.
2. Приложение FastAPI создает асинхронный пул соединений к БД через asyncpg.
3. При запросе POST /deadlines данные валидируются через Pydantic, сохраняются в БД через SQLAlchemy, и сервер мгновенно возвращает ответ 201 Created.
4. Параллельно (не блокируя ответ клиенту) запускается фоновая корутина send_deadline_notification, которая пытается отправить письмо через SMTP. Если SMTP-сервер недоступен, ошибка перехватывается (try/except), не влияя на работу основного API (graceful degradation).
5. При запросе GET /deadlines/{user_id} приложение динамически формирует SQL-запрос, добавляя условия WHERE category = ... или WHERE priority = ..., если они переданы в query-параметрах.
6. Во время тестирования зависимость get_db переопределяется (app.dependency_overrides), перенаправляя все запросы к временной in-memory базе данных SQLite для полной изоляции и скорости.