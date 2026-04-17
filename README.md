# shabash-aggregator

Система агрегации заявок на разовые низкоквалифицированные работы из VK и Telegram
с ML-фильтрацией и LLM-извлечением атрибутов. Подробное ТЗ — в `local/тз_финальное.md`.

## Стек

Python 3.12 · PostgreSQL 16 · Redis 7 (Streams) · SQLAlchemy async · Alembic · httpx · pydantic-settings.

## Запуск инфраструктуры

```bash
docker compose up -d        # поднимает PostgreSQL и Redis
alembic upgrade head        # накатывает схему БД
```

Переменные окружения берутся из `.env` (см. `.env.example`).

## VK scraper

Реализован сквозной путь: VK scraper собирает посты из активных сообществ
(`groups_vk.is_active = true`), сохраняет их в БД (`posts`, `posts_details_vk`,
`attachments`), выполняет дедупликацию и публикует доменный объект `Post`
в Redis-поток `new_posts`, откуда их забирает грубый фильтр.

### Предусловия

1. В `.env` задан валидный `VK_TOKEN`.
2. В таблице `groups_vk` есть хотя бы одна активная запись.
   `group_id` хранится как **отрицательный** owner_id сообщества (например, `-167102108`).
3. Подняты PostgreSQL и Redis, миграции накатаны.

### Запуск воркеров

В отдельных терминалах (с активированным venv):

```bash
# 1. Сборщик VK: опрашивает активные сообщества и пишет в new_posts
python -m app.workers.vk_scraper_worker

# 2. Грубый фильтр: читает new_posts, отсекает текст < 30 символов,
#    прошедшие со статусом coarse_filter_passed отправляет в candidate_posts
python -m app.workers.coarse_filter_worker

# 3. ML-фильтр: читает candidate_posts, классифицирует релевантность
#    обученной моделью (models/relevance_clf.joblib), прошедшие со статусом
#    ml_filter_passed отправляет в filtered_posts
#    (нужна обученная модель — см. app/ml/README.md)
python -m app.workers.ml_filter_worker

# 4. Извлечение атрибутов: читает filtered_posts, через LLM извлекает
#    длительность/характер работы/оплату/адрес, пишет в attributes,
#    статус attributes_extracted, отправляет в prepared_posts
python -m app.workers.attribute_extractor_worker

# 5. Публикаторы: каждый своей consumer group читает prepared_posts и
#    постит заявку «как есть» в свой канал (VK с перезаливкой фото)
python -m app.workers.vk_group_publisher_worker
python -m app.workers.tg_channel_publisher_worker

# 6. Персональные боты: меню/фильтры + рассылка заявок подписчикам
#    по их пользовательским фильтрам (TG — aiogram, VK — Long Poll)
python -m app.workers.tg_bot_worker
python -m app.workers.vk_bot_worker
```

### Персональные боты

Пользователь пишет боту → /start → приветствие + меню (⚙ настройки, 🎧 поддержка,
🚫 пауза). В настройках — мастер из вопросов: фильтры по оплате/адресу, характеру
работы (грузчик/разнорабочий/специалист/не определён) и длительности (короткая/
смена/постоянная/вахта/не определена). По умолчанию новый пользователь получает всё.

Бот-воркер делает две вещи параллельно: принимает апдейты (меню/мастер) и читает
`prepared_posts` своей consumer group, рассылая каждую заявку активным подписчикам,
у кого она проходит фильтры. Данные пользователей — в таблицах `tg_bot_users` /
`vk_bot_users`.

Нужны в `.env`: `TG_BOT_DISPATCH_TOKEN` (отдельный бот @BotFather); для VK
переиспользуются `VK_PUBLISH_TOKEN` (с правом «Сообщения») и `VK_PUBLISH_GROUP_ID`
(в сообществе включены «Сообщения» и Long Poll API с событиями message_new/message_allow).

### Чистый запуск «с этого момента»

Чтобы скраперы не подтянули старые публикации (для источников с пустым
`last_seen` это до 50 штук), сначала проставь курсоры на текущий последний пост:
```bash
python -m app.workers.seed_cursors            # только источники с пустым курсором
python -m app.workers.seed_cursors --all      # все активные (старт строго с этого момента)
```
После этого в пайплайн пойдут только заявки, появившиеся после сидинга.

### Извлечение атрибутов (LLM)

Модуль `attribute_extractor` использует OpenAI-совместимый LLM (по умолчанию
OpenRouter + Qwen, см. `LLM_*` в `.env`). Управление режимом:
- `LLM_ENABLED=false` (по умолчанию) — заглушка: всё `UNKNOWN`/`None`, без вызовов LLM
  (удобно гонять конвейер без трат). `LLM_ENABLED=true` — реальные вызовы (нужен `LLM_API_KEY`).
- При сбое LLM/валидации сообщение остаётся pending и переобработается.

Ручная проверка извлечения без пайплайна:
```bash
python -m app.modules.attribute_extractor.cli --text "на сейчас, бургасская 43, 1 чел занести штукатурку, 500/2"
python -m app.modules.attribute_extractor.cli --post-id 123
python -m app.modules.attribute_extractor.cli --text "..." --stub   # заглушка
```

Сборщик опрашивает VK каждые `VK_POLL_INTERVAL` секунд (по умолчанию 60).
На первом проходе по каждой группе берётся только последняя страница стены
(история целиком не загружается); далее обрабатываются только посты новее
`last_seen_post_id`.

## Telegram scraper

Собирает новые сообщения из активных Telegram-чатов (`chats_tg.is_active = true`)
через Telethon (client API, не Bot API), сохраняет их в `posts` / `posts_details_tg`,
дедуплицирует и публикует в тот же поток `new_posts`. Вложения в MVP не сохраняются.

### Предусловия

1. В `.env` заданы `TG_API_ID` и `TG_API_HASH` (получить на https://my.telegram.org).
2. Аккаунт-клиент состоит во всех целевых чатах.
3. В `chats_tg` есть активные записи. `chat_id` хранится в формате
   marked id (`-100…`, например `-1001950740300`), `url` — ссылка на чат.

### Первичный логин (один раз)

```bash
python -m app.workers.tg_login
```

Скрипт спросит номер телефона и код из Telegram (и пароль 2FA, если включён)
и создаст файл сессии `<TG_SESSION_NAME>.session`. Дальше воркер стартует молча.

### Запуск воркера

```bash
python -m app.workers.tg_scraper_worker
```

Опрашивает чаты каждые `TG_POLL_INTERVAL` секунд. На первом проходе берёт
последние `TG_MESSAGES_PER_REQUEST` сообщений чата; далее идёт от
`last_seen_message_id` вперёд. FloodWait до `TG_FLOOD_SLEEP_THRESHOLD` секунд
Telethon пережидает сам, более долгий — чат пропускается до следующего цикла.

### Проверка

- В логах сборщика — число новых постов по каждой группе.
- В логах грубого фильтра — строки `post id=... -> coarse_filter_passed|coarse_filter_rejected`.
- В Redis: `redis-cli XLEN new_posts`, `redis-cli XLEN candidate_posts`.
- В БД: `SELECT status, count(*) FROM posts GROUP BY status;`

Чтобы прогнать через фильтр уже накопленные в `new_posts` сообщения заново,
сбросьте позицию consumer group на начало стрима **перед** запуском воркера:

```bash
redis-cli XGROUP SETID new_posts coarse_filter 0
```

## Тесты / smoke-скрипты

```bash
python -m tests.test_coarse_filter                          # юнит-тест грубого фильтра
python -m tests.test_tg_mapper                              # юнит-тест маппера TG
python -m tests.test_attribute_extractor                    # юнит-тест извлечения атрибутов
python -m tests.test_bot_conversation                       # юнит-тест меню/фильтров бота
python -m app.workers.vk_scraper_process_group_smoke_test   # VK scraper на фейках
python -m app.workers.vk_mapper_smoke_test                  # маппер VK
python -m app.workers.redis_smoke_test                      # транспорт Redis (нужен Redis)
```
