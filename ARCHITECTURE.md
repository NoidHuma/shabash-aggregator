# Shabash Aggregator — устройство проекта

Документ для разработчика, который видит проект впервые. Подробно описывает суть,
архитектуру и — главное — **устройство кода**: какие модули за что отвечают, как
данные текут через систему, какие контракты связывают слои.

---

## 1. Что это и зачем

**Shabash Aggregator** — конвейер (pipeline) для сбора, фильтрации, обогащения и
рассылки объявлений о подработке («шабашках») в Краснодаре.

Бизнес-сценарий:

1. Из публичных **VK-групп** и **Telegram-каналов/чатов** непрерывно собираются новые посты.
2. Посты проходят через несколько ступеней очистки: грубый фильтр по длине → ML-классификатор
   релевантности → извлечение структурированных атрибутов через LLM.
3. Готовые («обогащённые») посты публикуются в собственный **VK-сообщество** и
   **Telegram-канал**, а также рассылаются адресно подписчикам двух ботов (VK и TG) —
   с учётом персональных фильтров каждого пользователя.

Ключевая ценность: из «грязного» потока сообщений на выходе получается единый формат —
заявка с распознанными полями: **длительность**, **характер работы**, **оплата**, **адрес**.

---

## 2. Архитектура с высоты птичьего полёта

Система построена как набор **независимых воркеров-процессов**, общающихся через
**Redis Streams** (брокер сообщений). Каждая ступень — отдельный контейнер. Источник
истины (persisted state) — **PostgreSQL**.

```
   VK API ─┐                                                       ┌─→ VK-сообщество (vk_group_publisher)
           │  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐  ├─→ TG-канал      (tg_channel_publisher)
   TG API ─┴─→│ scrapers │──→│  coarse  │──→│    ml    │──→│attribute │──┤
              │ (vk, tg) │   │  filter  │   │  filter  │   │extractor │  ├─→ VK-бот подписчикам (vk_bot)
              └────┬─────┘   └────┬─────┘   └────┬─────┘   └────┬─────┘  └─→ TG-бот подписчикам (tg_bot)
                   │              │              │              │
            new_posts      candidate_posts  filtered_posts  prepared_posts   ← имена Redis-стримов
                   │              │              │              │
                   └──────────────┴──────────────┴──────────────┘
                              PostgreSQL (status-машина поста)
```

### 2.1. Конвейер из Redis-стримов

Стримы и группы объявлены в одном месте — [app/constants/streams.py](app/constants/streams.py):

| Стрим               | Кто пишет                | Кто читает (consumer group)                          |
|---------------------|--------------------------|------------------------------------------------------|
| `new_posts`         | scrapers (vk, tg)        | `coarse_filter`                                      |
| `candidate_posts`   | coarse_filter            | `ml_filter`                                          |
| `filtered_posts`    | ml_filter                | `attribute_extractor`                               |
| `prepared_posts`    | attribute_extractor      | `vk_group_publisher`, `tg_channel_publisher`, `vk_bot_dispatcher`, `tg_bot_dispatcher` |

Важный приём: **`prepared_posts` читают сразу четыре независимые consumer-группы**. Redis
Streams доставляет каждое сообщение каждой группе по отдельности (fan-out), поэтому один
готовый пост одновременно уходит в публикацию на канал/сообщество и в адресную рассылку ботов.

### 2.2. Status-машина поста в БД

Параллельно с прохождением по стримам каждый пост меняет `status` в таблице `posts`
([app/enums/post_status.py](app/enums/post_status.py)):

```
NEW
 ├─ COARSE_FILTER_PASSED ─┬─ ML_FILTER_PASSED ── ATTRIBUTES_EXTRACTED
 │                        └─ ML_FILTER_REJECTED
 └─ COARSE_FILTER_REJECTED
```

Стрим — это «транспорт между ступенями», а статус в БД — «журнал того, до какой ступени
пост дошёл». Отклонённые посты остаются в БД (для аналитики/датасета), но дальше по стриму
не идут.

---

## 3. Технологический стек

| Слой              | Технология                                                             |
|-------------------|------------------------------------------------------------------------|
| Язык              | Python 3.12, всё на `asyncio`                                          |
| Брокер сообщений  | Redis 7 (Streams + consumer groups), `redis.asyncio`                  |
| БД                | PostgreSQL 16, SQLAlchemy 2.0 (async, `asyncpg`), Alembic-миграции    |
| Конфиг            | `pydantic-settings` (env → типизированный `Settings`)                 |
| Telegram (скрап)  | Telethon (MTProto, user-сессия)                                       |
| Telegram (боты/публикация) | aiogram 3 + сырой Bot API через httpx                       |
| VK                | сырой VK API через httpx (wall.get, wall.post, Long Poll)             |
| ML                | scikit-learn (TF-IDF + LogReg/SVM/NB), сериализация через joblib      |
| LLM               | OpenAI-совместимый клиент (по умолчанию Mistral API)                  |
| Деплой            | Docker Compose, по контейнеру на воркер                              |

Зависимости зафиксированы в [requirements.txt](requirements.txt).

---

## 4. Карта каталогов

```
app/
├── constants/streams.py     # имена Redis-стримов и consumer-групп — единый источник
├── core/                    # инфраструктура: config, logging, redis-клиент
├── db/database.py           # async engine + sessionmaker + Base
├── domain/                  # «чистые» dataclass-ы, летающие по стримам (Post, PostAttributes)
├── enums/                   # PostSource, PostStatus, DurationType, WorkType
├── models/                  # SQLAlchemy ORM-таблицы
├── repositories/            # доступ к БД (по таблице на репозиторий)
├── services/                # переиспользуемая логика без состояния (сериализация, хеш, формат)
├── modules/                 # «толстые» доменные модули, по одному на внешнюю интеграцию
│   ├── tg_scraper/          #   скрапинг Telegram (client + scraper + mapper)
│   ├── vk_scraper/          #   скрапинг VK
│   ├── coarse_filter/       #   грубый фильтр
│   ├── ml_filter/           #   ML-классификатор
│   ├── attribute_extractor/ #   LLM-извлечение атрибутов (extractor + llm_client + prompt)
│   ├── bots/                #   логика диалога ботов (конечный автомат, общая для VK и TG)
│   ├── tg_publisher.py      #   публикация в TG-канал
│   ├── vk_publisher.py      #   публикация в VK-сообщество
│   └── vk_bot.py            #   VK Bot API (Long Poll + отправка)
├── workers/                 # точки входа процессов (по одному `python -m` на воркер)
├── ml/                      # офлайн-обучение классификатора (train, data, preprocessing)
└── utils/                   # seed_cursors (инициализация курсоров), tg_login (логин в TG)
alembic/                     # миграции схемы БД
data/                        # датасеты для ML и seed_sources.sql (список источников)
docker-compose.yml           # оркестрация всех контейнеров
```

### Принцип слоёв (важно для понимания кода)

Проект последовательно разделяет три представления одного «поста»:

1. **ORM-модель** ([app/models/posts.py](app/models/posts.py)) — то, что лежит в БД
   (`status`, `text_hash`, `post_datetime`, `created_at` и т.д.).
2. **Доменный `Post`** ([app/domain/post.py](app/domain/post.py)) — лёгкий `dataclass`
   без полей БД, который сериализуется в JSON и летает по стримам между воркерами.
3. **Отформатированный текст** ([app/services/post_formatter.py](app/services/post_formatter.py))
   — готовое к показу человеку сообщение.

Преобразования между ними делают **mapper-ы** (в модулях скраперов) и **сериализатор**
([app/services/post_serializer.py](app/services/post_serializer.py)).

---

## 5. Доменные модели и контракты

### 5.1. Доменный `Post` — то, что летает по стримам

[app/domain/post.py](app/domain/post.py):

```python
@dataclass
class Post:
    id: int                      # PK из таблицы posts
    source: PostSource           # TG | VK
    text: str
    source_post_url: str         # ссылка на исходную публикацию
    source_chat_url: str         # ссылка на исходный чат/группу
    attachments: list[str]       # URL-ы фото
    attributes: PostAttributes | None  # None, пока атрибуты не извлечены
```

`attributes` заполняется только на ступени `attribute_extractor`; до неё — `None`.

### 5.2. `PostAttributes` — результат LLM-извлечения

[app/domain/post_attributes.py](app/domain/post_attributes.py):

```python
@dataclass
class PostAttributes:
    duration: DurationType    # permanent | full_shift | short_task | vahta | unknown
    work_type: WorkType       # loader | handyman | specialist | unknown
    payment: str | None       # дословный фрагмент из текста или None
    address: str | None
```

Enum-ы — в [app/enums/](app/enums/). `duration` и `work_type` всегда имеют значение
(хотя бы `UNKNOWN`), а `payment`/`address` опциональны.

### 5.3. Сериализация для стрима

[app/services/post_serializer.py](app/services/post_serializer.py) превращает `Post` в
одно Redis-поле `payload` с JSON-строкой (`ensure_ascii=False`, чтобы кириллица читалась)
и обратно. Enum-ы сериализуются по `.value`. Это единственный контракт «как пост выглядит
в стриме» — обе стороны (publish/read) ходят через эти две функции.

---

## 6. Слой работы с БД

### 6.1. Подключение

[app/db/database.py](app/db/database.py): async-engine на `asyncpg`, `async_sessionmaker`
с `expire_on_commit=False` (чтобы после commit объекты оставались доступны), декларативный `Base`.

`expire_on_commit=False` существенен: воркеры читают поля ORM-объекта уже после `commit()`
(например, `mapper.build_domain_post` берёт `post.id`), что без этого флага вызвало бы
повторный запрос/ошибку отсоединённого объекта.

### 6.2. ORM-таблицы ([app/models/](app/models/))

| Модель              | Таблица              | Назначение                                                |
|---------------------|----------------------|-----------------------------------------------------------|
| `Post`              | `posts`              | центральная таблица: текст, статус, источник, `text_hash` |
| `PostAttributes`    | `attributes`         | 1-к-1 с постом, результат LLM                            |
| `Attachment`        | `attachments`        | фото поста (url + position)                              |
| `PostDetailsTG`     | `posts_details_tg`   | TG-специфика: `chat_id`, `message_id`, `sender_id`       |
| `PostDetailsVK`     | `posts_details_vk`   | VK-специфика: `owner_id`, `vk_post_id`, `from_id`        |
| `ChatTG`            | `chats_tg`           | список TG-источников + курсор `last_seen_message_id`     |
| `GroupVK`           | `groups_vk`          | список VK-источников + курсор `last_seen_post_id`        |
| `TGBotUser`/`VKBotUser` | `tg_bot_users`/`vk_bot_users` | подписчики ботов и их фильтры          |

`TGBotUser` и `VKBotUser` делят общий `_BotUserMixin` ([app/models/bot_users.py](app/models/bot_users.py))
— идентичный набор полей-флагов фильтров (`src_vk`, `wt_loader`, `dur_vahta`, …) плюс поля
состояния визарда (`wizard_step`, `wizard_draft`, `wizard_mode`).

### 6.3. Репозитории ([app/repositories/](app/repositories/))

Тонкий слой доступа: по репозиторию на таблицу, методы принимают `session` снаружи (сессией
владеет вызывающий воркер, репозиторий её не открывает и не коммитит). Это позволяет одному
воркеру в одной транзакции писать сразу в несколько таблиц.

Примеры значимых методов:

- `PostsRepository.exists_hash_last_hour` — дедупликация по хешу текста за последний час.
- `PostsRepository.create_post` делает `flush()` (не `commit`), чтобы получить
  сгенерированный `id`, оставляя транзакцию открытой.
- `AttributesRepository.create_or_update` — upsert атрибутов (идемпотентность при повторной
  обработке).
- `BotUsersRepository` — параметризован моделью (`__init__(self, model)`), поэтому один класс
  обслуживает и TG-, и VK-пользователей.

---

## 7. Скраперы — вход в систему

Оба скрапера устроены одинаково (client → scraper → mapper) и пишут в `new_posts`.

### 7.1. Telegram ([app/modules/tg_scraper/](app/modules/tg_scraper/))

- **`tg_client.py`** — обёртка над Telethon. Работает на **user-сессии** (не bot-token):
  файл `tg_scraper.session` монтируется в контейнер. `get_new_messages` использует
  `min_id=last_seen_message_id` + `reverse=True`, чтобы тянуть только новое и по порядку.
  `warm_entity_cache()` дёргает `get_dialogs()` — без этого Telethon не знает entity приватных
  каналов.
- **`scraper.py`** — `TGScraper.process_chat` для каждого сообщения:
  1. `is_processable_message` — отсеивает служебные сообщения, стикеры, документы-не-видео,
     пустой текст ([mapper.py](app/modules/tg_scraper/mapper.py)).
  2. Дедуп по источнику (`exists_tg_message` — этот `chat_id`+`message_id` уже видели?).
  3. Дедуп по тексту (`exists_hash_last_hour` — такой же текст за час из любого источника?).
  4. Сохраняет `Post` + `PostDetailsTG` в одной транзакции, коммитит, публикует доменный пост в стрим.
  5. **Всегда** обновляет курсор `last_seen_message_id` (даже для отброшенных) — чтобы не
     перечитывать их снова.
- **`mapper.py`** — преобразование Telethon-сообщения в ORM `Post` и `PostDetailsTG`,
  построение URL публикации (`t.me/username/id` или `t.me/c/internal_id/id`), нормализация
  времени к naive-UTC (как у VK).

### 7.2. VK ([app/modules/vk_scraper/](app/modules/vk_scraper/))

- **`vk_client.py`** — сырой VK API через httpx с тремя механизмами устойчивости:
  - **throttle** (`asyncio.Lock` + `_min_interval`) — не превышать `VK_REQUESTS_PER_SECOND`;
  - **ретраи с экспоненциальным backoff** на сетевые ошибки и `error_code 6` (Too many requests);
  - явное исключение `VKAccessDeniedError` на `error_code 15` (закрытая группа).
- **`scraper.py`** — `VKScraper.process_group`. Логика сложнее, чем у TG, из-за пагинации:
  `_collect_new_posts` идёт по стене страницами (`wall.get` с offset), собирая всё новее
  `last_seen_post_id`, **отдельно обрабатывая закреплённые посты** (`is_pinned` — у них id может
  быть «старым», их не считают границей остановки) и упираясь в потолок `MAX_WALL_OFFSET = 1000`.
  Далее — те же ступени: пропуск пустых и `marked_as_ads`, дедуп по источнику и по тексту,
  сохранение `Post` + `PostDetailsVK` + `Attachment`-ы, публикация, сдвиг курсора.
- **`mapper.py`** — извлечение текста, времени (`utcfromtimestamp`), URL (`vk.com/wall{owner}_{id}`)
  и фото: из всех размеров вложения берётся самый большой по площади (`extract_photo_urls`).

### 7.3. Дедупликация (общий механизм)

[app/services/hash_service.py](app/services/hash_service.py): `normalize_text` приводит к
нижнему регистру и вырезает всё, кроме букв/цифр (`\W+`, юникод), затем sha256. Один и тот же
текст, перепощенный в разные группы с разным оформлением, схлопывается в один хеш. Дедуп
ограничен окном в 1 час (`exists_hash_last_hour`) — чтобы периодически повторяющиеся легитимные
объявления всё же проходили.

---

## 8. Ступени фильтрации и обогащения

Все три воркера-обработчика устроены по **одному шаблону** (см. ниже) — это центральный паттерн
кода, который стоит понять один раз.

### 8.1. Общий шаблон воркера-обработчика стрима

Каждый из `coarse_filter_worker`, `ml_filter_worker`, `attribute_extractor_worker` (а также
публикаторы и диспетчеры ботов) крутит один и тот же цикл через `StreamService`
([app/services/stream_service.py](app/services/stream_service.py)):

```python
while True:
    # 1) сначала «спасаем» зависшие у мёртвых консьюмеров сообщения
    for msg in await stream.claim_stale_posts(in_stream, group, consumer):
        handle(msg)
    # 2) затем читаем новые
    for msg in await stream.read_posts(in_stream, group, consumer):  # XREADGROUP, block=5s
        handle(msg)
```

Где `handle(msg)`:
1. Выполняет работу ступени (фильтр/ML/LLM/публикация).
2. Обновляет статус в БД и/или публикует пост в выходной стрим.
3. **Только при успехе** делает `ack` (XACK).

**Гарантия доставки — at-least-once.** Если на шаге упало исключение — `ack` не вызывается,
сообщение остаётся в Pending Entries List группы. `claim_stale_posts` (XAUTOCLAIM с
`min_idle_ms`) на следующих итерациях заберёт «застрявшие» сообщения и переобработает.
Поэтому все операции записи спроектированы идемпотентно (upsert атрибутов, update статуса,
дедуп по источнику).

`StreamService.ensure_group` создаёт consumer-группу лениво при первом чтении
(`mkstream=True`, игнорируя `BUSYGROUP`), так что порядок старта воркеров не важен.

### 8.2. Coarse filter ([app/modules/coarse_filter/](app/modules/coarse_filter/) + worker)

Самая дешёвая ступень-привратник. Вся логика — одна функция:

```python
MIN_TEXT_LENGTH = 30
def passes_coarse_filter(post): return len(post.text) >= MIN_TEXT_LENGTH
```

Прошёл → `COARSE_FILTER_PASSED` + публикация в `candidate_posts`; нет → `COARSE_FILTER_REJECTED`,
дальше не идёт. Отсекает «спасибо», «+», эмодзи и прочий короткий шум до того, как тратиться на ML.

### 8.3. ML filter ([app/modules/ml_filter/](app/modules/ml_filter/) + worker)

Классификатор релевантности: «это реальное объявление о работе» vs «болтовня/реклама/вопрос».

- **`classifier.py`** — `RelevanceClassifier` оборачивает обученный sklearn-`Pipeline`,
  загружаемый из `.joblib`-бандла (`pipeline` + `threshold` + `metadata`). `predict_proba`
  возвращает вероятность класса «1», сравнивается с порогом.
- **worker** — на старте проверяет наличие файла модели, грузит её, логирует порог и метаданные.
  `proba >= threshold` → `ML_FILTER_PASSED` + публикация в `filtered_posts`; иначе `ML_FILTER_REJECTED`.

Порог хранится **в самом бандле модели** (подбирается при обучении), а не в конфиге — чтобы
модель и её рабочая точка всегда были согласованы.

### 8.4. Attribute extractor ([app/modules/attribute_extractor/](app/modules/attribute_extractor/) + worker)

Самая «умная» ступень: LLM превращает свободный текст в 4 структурированных поля.

- **`prompt.py`** — `SYSTEM_PROMPT` с подробными правилами классификации (что считать `vahta`,
  чем `loader` отличается от `handyman` и т.д.) + большой набор **few-shot** примеров
  `(текст → ожидаемый JSON)`. Это «обучение» модели прямо в промпте.
- **`llm_client.py`** — `LLMClient` поверх OpenAI-совместимого SDK (по умолчанию Mistral):
  - собирает messages = system + few-shot пары + текст пользователя;
  - запрос с `temperature=0` и `response_format={"type": "json_object"}` (строгий JSON);
  - собственный **throttle** (потокобезопасный, через `threading.Lock`, т.к. SDK синхронный)
    под `LLM_REQUESTS_PER_SECOND`;
  - ретраи с экспоненциальной задержкой, парсинг `json.loads`.
- **`extractor.py`** — две реализации за общим `Protocol`-интерфейсом:
  - `LLMExtractor` — реальный вызов + маппинг JSON в `PostAttributes`. `_parse_enum` устойчиво
    мапит строку LLM в enum (по value или по имени, иначе `UNKNOWN`); `_clean_optional`
    нормализует «null»/«не указано»/«-» в `None`.
  - `StubExtractor` — заглушка (всё `UNKNOWN`/`None`), без обращений к LLM.
  - `build_extractor()` выбирает по флагу `LLM_ENABLED` — удобно отключать LLM в dev/тестах.
- **worker** — вызывает синхронный `extractor.extract` через `asyncio.to_thread` (чтобы не
  блокировать event loop), делает upsert атрибутов + статус `ATTRIBUTES_EXTRACTED` в одной
  транзакции, публикует обогащённый пост в `prepared_posts`.

---

## 9. Публикация и рассылка

`prepared_posts` потребляют четыре независимые группы (см. §2.1).

### 9.1. Форматирование ([app/services/post_formatter.py](app/services/post_formatter.py))

`format_post` собирает человекочитаемое сообщение с эмодзи и человекочитаемыми лейблами
enum-ов (`DurationType.VAHTA → "Вахта"`, `WorkType.LOADER → "Грузчик"`), с fallback
«не удалось определить» для `UNKNOWN`/`None`. Внизу — исходный текст и ссылки на источник.
Один и тот же форматтер используют все каналы вывода (единый внешний вид заявки).

### 9.2. Политика канала ([app/services/publish_policy.py](app/services/publish_policy.py))

```python
_AGGREGATOR_EXCLUDED_DURATIONS = {DurationType.PERMANENT, DurationType.VAHTA}
def allowed_in_aggregator(post): ...  # постоянка и вахта НЕ идут в общий канал/сообщество
```

Публичный агрегатор (канал/сообщество) — про разовые подработки, поэтому постоянную работу и
вахту он отсекает. **Боты этим фильтром не пользуются** — там пользователь сам решает через
персональные настройки.

### 9.3. Публикаторы

- **`tg_publisher.py`** (`TGChannelPublisherWorker` + `TGPublisherClient`) — публикация в
  TG-канал через сырой Bot API (httpx): `sendMessage` + при наличии фото `sendPhoto`/
  `sendMediaGroup` ответом на текст. Обрабатывает `retry_after` (429), режет текст до 4096 и
  медиа до 10. После каждой публикации — пауза `publish_min_interval`.
- **`vk_publisher.py`** (`VKPublisherClient`) — `wall.post` от имени сообщества. Фото требует
  **отдельного user-токена** (`VK_PUBLISH_USER_TOKEN`): загрузка через
  `photos.getWallUploadServer` → upload → `photos.saveWallPhoto`. Если user-токена нет — пост
  уходит без фото (с предупреждением).

### 9.4. Боты (адресная рассылка с фильтрами)

Два воркера — `tg_bot_worker` и `vk_bot_worker` — каждый делает **две вещи одновременно**
(`asyncio.gather`):

1. **Диалог с пользователем** (входящие сообщения/нажатия кнопок) — настройка персональных фильтров.
2. **dispatch_loop** — читает `prepared_posts` и шлёт пост каждому активному подписчику,
   **чей фильтр совпал** (`filters.matches`).

Вся доменная логика диалога вынесена в общий, не зависящий от платформы модуль
[app/modules/bots/](app/modules/bots/) — а воркеры лишь адаптируют её под конкретный
транспорт (aiogram для TG, VK Long Poll для VK).

---

## 10. Логика ботов — конечный автомат настроек

Это самая нетривиальная по объёму логика после конвейера. Ключевая идея: **одна и та же
логика обслуживает оба мессенджера**; различается только транспортный адаптер.

### 10.1. Общий модуль [app/modules/bots/](app/modules/bots/)

- **`wizard.py`** — декларативное описание всех фильтров. `FILTERS: list[FilterDef]` — список
  «вопросов»: текст, варианты, и `assignments` (какие булевы поля модели выставить для каждого
  варианта). 12 фильтров: источники, требование оплаты/адреса, 4 типа работы, 5 типов
  длительности. `CATEGORIES` группирует их для меню «изменить один фильтр». Здесь же —
  рендер сводки текущих настроек (`summary_text`).
- **`conversation.py`** — чистый, не зависящий от платформы конечный автомат:
  - `handle_command(user, text, is_new)` → список `Out` (для входящих текстов: `/start`, приветствие новичка).
  - `handle_callback(user, data)` → один `Out` (для нажатий кнопок: навигация по меню,
    прохождение визарда по шагам, сохранение черновика).
  - `Out(text, keyboard, edit)` — платформонезависимое описание «что показать»: текст +
    абстрактная клавиатура + флаг «редактировать прошлое сообщение или прислать новое».
  - Состояние визарда живёт **в полях пользователя в БД** (`wizard_step`, `wizard_draft` как
    JSON, `wizard_mode`), а не в памяти процесса — поэтому диалог переживает рестарт воркера
    и работает при нескольких репликах.
- **`keyboards.py`** / **`texts.py`** — абстрактные клавиатуры (`Keyboard`, `Button` с label/data/color)
  и все тексты сообщений.
- **`filters.py`** — `matches(user, post)`: применяет булевы флаги пользователя к атрибутам
  поста. Решает, слать ли конкретному подписчику конкретную заявку (по источнику, наличию
  оплаты/адреса, типу работы, длительности).

### 10.2. Транспортные адаптеры

- **`tg_bot_worker.py`** — aiogram-`Dispatcher`: `@dp.message`/`@dp.callback_query` достают
  пользователя из БД, зовут `handle_command`/`handle_callback`, превращают абстрактную
  `Keyboard` в `InlineKeyboardMarkup` (`_to_tg_kb`) и отвечают.
- **`vk_bot.py`** + **`vk_bot_worker.py`** — то же, но через VK Long Poll
  (`groups.getLongPollServer` → бесконечный `poll`): события `message_new`/`message_event`
  маппятся в те же `handle_command`/`handle_callback`, абстрактная клавиатура конвертируется
  в VK-формат (`to_vk_keyboard`).

Таким образом, чтобы изменить логику настроек или набор фильтров, правишь **только** `bots/*` —
оба бота подхватывают изменение автоматически.

---

## 11. ML: офлайн-обучение классификатора

Каталог [app/ml/](app/ml/) — отдельный офлайн-инструмент (не часть рантайма), который
производит `.joblib`-модель для `ml_filter`.

- **`data.py`** — `load_samples`: читает размеченный CSV (`label` 0/1, `text`), отбрасывает
  слишком короткие (`min_length=30`, согласовано с coarse-фильтром).
- **`preprocessing.py`** — `clean_text`: убирает zero-width символы, `\xa0`, схлопывает пробелы,
  нижний регистр. Тот же препроцессор зашит в векторайзеры пайплайна (важно: при инференсе
  применяется автоматически).
- **`train.py`** — основной скрипт (`python -m app.ml.train`):
  - **признаки**: `FeatureUnion` из двух TF-IDF — словесные n-граммы (1–2) и символьные
    char_wb n-граммы (3–5). Символьные хорошо ловят опечатки и слитное написание.
  - **модели-кандидаты**: `logreg` (по умолчанию, `class_weight="balanced"`), `svm`
    (калиброванный LinearSVC), `nb` (MultinomialNB).
  - **бенчмарк**: стратифицированная кросс-валидация с `classification_report` по всем трём.
  - **подбор порога**: либо под целевую precision (`--target-precision`), либо по максимуму
    macro-F1 — через `cross_val_predict` с `predict_proba`.
  - сохраняет бандл `{pipeline, threshold, metadata}` (`save_classifier.py`); в `metadata` —
    версия sklearn/python, дата, состав классов (для воспроизводимости/совместимости).
- датасеты — в [data/dataset/](data/dataset/) (`train.csv`/`test.csv` и сырые/размеченные дампы).

Цикл: разметить CSV → `train.py` → `models/relevance_clf.joblib` → перезапустить `ml_filter`.

---

## 12. Конфигурация и инфраструктура

### 12.1. Settings ([app/core/config.py](app/core/config.py))

Единый `pydantic-settings` `Settings`, читающий `.env`. Группы: PostgreSQL, Redis, TG-скрапинг,
VK-скрапинг, путь к ML-модели, LLM, публикаторы, токены ботов. Импортируется как синглтон
`settings` по всему коду. Шаблон значений — [.env.example](.env.example).

### 12.2. Docker Compose ([docker-compose.yml](docker-compose.yml))

Один образ ([Dockerfile](Dockerfile)) — много контейнеров, каждый со своей `command`
(`python -m app.workers.<...>`). YAML-якоря `x-base`/`x-worker` убирают дублирование.

**Порядок старта оркестрируется зависимостями:**

1. `postgres`, `redis` — с healthcheck.
2. `migrate` — `alembic upgrade head` (ждёт здоровья postgres), `restart: no`.
3. `seed` — `seed_cursors --all` (ждёт успешного `migrate`), `restart: no`.
4. Все воркеры — `depends_on: seed (service_completed_successfully)`, `restart: unless-stopped`.

`tg_scraper`/`seed` монтируют `tg_scraper.session` (user-сессия Telethon), `ml_filter`
монтирует `./models:ro`.

### 12.3. Утилиты ([app/utils/](app/utils/))

- **`seed_cursors.py`** — инициализирует курсоры источников (`last_seen_*`) на «текущий
  последний пост», чтобы при первом запуске система **не вычитала всю историю** групп/чатов, а
  начала с новых публикаций. `--all` пересидит все активные источники; без флага — только те,
  где курсор пустой.
- **`tg_login.py`** — разовый интерактивный логин в Telegram для создания файла сессии.

### 12.4. Миграции и список источников

- [alembic/versions/](alembic/versions/) — эволюция схемы (стартовая схема, `last_seen`-курсоры,
  тип длительности `vahta`, таблицы пользователей ботов, поля фильтров и режим визарда).
- [data/seed_sources.sql](data/seed_sources.sql) — идемпотентный (`ON CONFLICT`) список
  VK-групп и TG-чатов для скрапинга. Курсоры `last_seen_*` он намеренно не трогает.

---

## 13. Сквозной поток одного поста (end-to-end)

Чтобы связать всё воедино, проследим путь одного объявления:

1. **Скрап.** `vk_scraper` видит новый пост на стене группы. Пропускает проверки (не пустой,
   не реклама, не дубль по источнику и по хешу текста за час). Пишет в БД `Post(status=NEW)`
   + `PostDetailsVK` + `Attachment`-ы (одна транзакция), сдвигает `last_seen_post_id`,
   публикует доменный `Post` в `new_posts`.
2. **Coarse.** `coarse_filter` читает из `new_posts`. `len(text) >= 30` → статус
   `COARSE_FILTER_PASSED`, публикация в `candidate_posts`, `ack`.
3. **ML.** `ml_filter` читает `candidate_posts`. `predict_proba(text) >= threshold` → статус
   `ML_FILTER_PASSED`, публикация в `filtered_posts`, `ack`.
4. **LLM.** `attribute_extractor` читает `filtered_posts`. LLM возвращает
   `{duration, work_type, payment, address}` → upsert в `attributes`, статус
   `ATTRIBUTES_EXTRACTED`, публикация **обогащённого** поста в `prepared_posts`, `ack`.
5. **Fan-out из `prepared_posts`** (4 группы параллельно):
   - `tg_channel_publisher`: если `allowed_in_aggregator` (не постоянка/вахта) — `format_post`
     и пост в TG-канал.
   - `vk_group_publisher`: аналогично в VK-сообщество.
   - `tg_bot_dispatcher`: для каждого активного TG-подписчика, чей `matches(user, post)` —
     личное сообщение.
   - `vk_bot_dispatcher`: то же для VK-подписчиков.

На каждой ступени сбой = отсутствие `ack` = повторная обработка позже (at-least-once),
а идемпотентные записи в БД делают повтор безопасным.

---

## 14. Сквозные принципы (что стоит держать в голове, читая код)

- **Один шаблон воркера.** Все обработчики стримов — это `claim_stale → read → handle → ack`.
  Поняв `coarse_filter_worker`, понимаешь структуру всех остальных.
- **Три представления поста** (ORM / domain / formatted) и явные mapper-ы/сериализаторы между ними.
- **Стрим = транспорт, статус в БД = журнал.** Не путать: продвижение по стриму и смена
  статуса идут рядом, но это разные механизмы.
- **At-least-once + идемпотентность.** `ack` только после успеха; все записи переживают повтор.
- **Платформонезависимое ядро ботов.** Логика диалога и фильтров не знает про aiogram/VK.
- **Внешние интеграции изолированы** в `modules/*` со своими клиентами, throttle и ретраями;
  остальной код от деталей VK/TG/LLM не зависит.
- **Состояние — в БД и Redis, не в памяти процесса.** Поэтому воркеры рестартуются и масштабируются
  без потери прогресса (курсоры источников, состояние визарда, pending-сообщения стримов).
- **Конфиг — один типизированный `settings`** из env; секреты и параметры не разбросаны по коду.

---

## 15. Точки входа (шпаргалка)

| Команда                                         | Что делает                                  |
|-------------------------------------------------|---------------------------------------------|
| `python -m alembic upgrade head`                | накатить миграции                           |
| `python -m app.utils.tg_login`                  | разовый логин в Telegram (создать сессию)   |
| `python -m app.utils.seed_cursors --all`        | инициализировать курсоры источников         |
| `python -m app.workers.vk_scraper_worker`       | скрапер VK                                  |
| `python -m app.workers.tg_scraper_worker`       | скрапер Telegram                            |
| `python -m app.workers.coarse_filter_worker`    | грубый фильтр                               |
| `python -m app.workers.ml_filter_worker`        | ML-фильтр релевантности                     |
| `python -m app.workers.attribute_extractor_worker` | LLM-извлечение атрибутов                 |
| `python -m app.workers.tg_channel_publisher_worker` | публикация в TG-канал                   |
| `python -m app.workers.vk_group_publisher_worker`   | публикация в VK-сообщество              |
| `python -m app.workers.tg_bot_worker`           | TG-бот (диалог + рассылка)                  |
| `python -m app.workers.vk_bot_worker`           | VK-бот (диалог + рассылка)                  |
| `python -m app.ml.train`                        | обучить ML-классификатор                    |
| `docker compose up -d`                          | поднять всё разом                           |
```
