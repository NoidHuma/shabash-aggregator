import json
import logging
import threading
import time

from openai import OpenAI

from app.core.config import settings
from app.modules.attribute_extractor.prompt import FEW_SHOT
from app.modules.attribute_extractor.prompt import SYSTEM_PROMPT


logger = logging.getLogger(__name__)


class LLMClient:
    """
    OpenAI-совместимый клиент (по умолчанию OpenRouter).

    Делает chat-completions запрос с принудительным JSON-выводом, парсит ответ
    в dict. На ошибки API и невалидный JSON делает повторы с бэкоффом; если так
    и не вышло — поднимает исключение (воркер оставит сообщение pending).
    """

    def __init__(
        self,
        api_key: str = settings.llm_api_key,
        base_url: str = settings.llm_base_url,
        model: str = settings.llm_model,
        timeout: float = settings.llm_timeout,
        max_retries: int = settings.llm_max_retries,
        requests_per_second: float = settings.llm_requests_per_second,
    ) -> None:
        if not api_key:
            raise RuntimeError("LLM_API_KEY не задан — заполни .env")

        self._model = model
        self._max_retries = max_retries
        # max_retries=0: свои повторы делаем сами (ниже), чтобы покрыть и JSON-сбои.
        self._client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout, max_retries=0)

        # Троттлинг: не чаще requests_per_second запросов в секунду.
        self._min_interval = 1.0 / requests_per_second if requests_per_second > 0 else 0.0
        self._throttle_lock = threading.Lock()
        self._last_request_at = 0.0

    def _throttle(self) -> None:
        """Выдерживает паузу под локом, чтобы соблюсти лимит запросов/сек."""
        if self._min_interval <= 0:
            return
        with self._throttle_lock:
            wait = self._min_interval - (time.monotonic() - self._last_request_at)
            if wait > 0:
                time.sleep(wait)
            self._last_request_at = time.monotonic()

    def _build_messages(self, text: str) -> list[dict]:
        messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
        for example_text, example_json in FEW_SHOT:
            messages.append({"role": "user", "content": example_text})
            messages.append({"role": "assistant", "content": example_json})
        messages.append({"role": "user", "content": text})
        return messages

    def extract_json(self, text: str) -> dict:
        messages = self._build_messages(text)

        last_error: Exception | None = None

        for attempt in range(self._max_retries + 1):
            try:
                self._throttle()
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    temperature=0,
                    response_format={"type": "json_object"},
                )
                content = response.choices[0].message.content or ""
                return json.loads(content)
            except Exception as error:  # API-ошибки и json.JSONDecodeError
                last_error = error
                if attempt < self._max_retries:
                    delay = 1.0 * (2 ** attempt)
                    logger.warning(
                        "LLM запрос не удался (%s), повтор %d/%d через %.1fс",
                        type(error).__name__,
                        attempt + 1,
                        self._max_retries,
                        delay,
                    )
                    time.sleep(delay)

        raise RuntimeError(f"LLM не вернул валидный JSON после повторов: {last_error}")
