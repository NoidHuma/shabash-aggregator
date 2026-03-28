# app/modules/vk_scraper/vk_client.py

import asyncio
import logging
import time

import httpx

from app.core.config import settings
from app.modules.vk_scraper.settings import VK_API_VERSION


logger = logging.getLogger(__name__)


# VK возвращает этот код при превышении частоты запросов
# ("Too many requests per second").
VK_TOO_MANY_REQUESTS = 6

# Стена закрыта: доступна только участникам сообщества.
VK_ACCESS_DENIED = 15


class VKAccessDeniedError(Exception):
    """
    Стена сообщества недоступна (например, закрыта для не-участников).

    Это устойчивая ошибка: повторять запрос бессмысленно, источник нужно
    либо сделать доступным (вступить в сообщество), либо деактивировать.
    """

    def __init__(
        self,
        owner_id: int | None,
        error_code: int,
        error_msg: str,
    ) -> None:
        self.owner_id = owner_id
        self.error_code = error_code
        self.error_msg = error_msg

        super().__init__(f"VK access denied (code {error_code}): {error_msg}")


class VKClient:
    """
    Клиент для работы с VK API.

    Учитывает лимиты и сбои VK:
    - глобальный троттлинг (не чаще vk_requests_per_second на один экземпляр
      клиента, т.е. на весь процесс-сборщик);
    - повтор запроса с экспоненциальным бэкоффом при error_code 6 и при
      сетевых сбоях (таймаут/обрыв соединения);
    - явная типизированная ошибка VKAccessDeniedError для закрытых стен.
    """

    BASE_URL = "https://api.vk.com/method"

    def __init__(
        self,
        requests_per_second: float = settings.vk_requests_per_second,
        max_retries: int = settings.vk_max_retries,
        request_timeout: float = settings.vk_request_timeout,
        retry_base_delay: float = 0.5,
    ) -> None:
        self._min_interval = (
            1.0 / requests_per_second if requests_per_second > 0 else 0.0
        )
        self._max_retries = max_retries
        self._request_timeout = request_timeout
        self._retry_base_delay = retry_base_delay

        self._throttle_lock = asyncio.Lock()
        self._last_request_at = 0.0

    async def get_latest_posts(
        self,
        owner_id: int,
        count: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """
        Получить посты со стены сообщества.

        owner_id — отрицательный идентификатор сообщества (например, -167102108).
        count — сколько постов вернуть за один запрос (VK ограничивает 100).
        offset — смещение от начала стены, нужно для постраничного обхода.
        """

        params = {
            "owner_id": owner_id,
            "count": count,
            "offset": offset,
            "access_token": settings.vk_token,
            "v": VK_API_VERSION,
        }

        response = await self._request(
            method="wall.get",
            params=params,
        )

        return response["items"]

    async def get_group_info(
        self,
        owner_id: int,
    ) -> dict:
        """
        Будет реализовано позже.
        """

        raise NotImplementedError

    async def _request(
        self,
        method: str,
        params: dict,
    ) -> dict:
        """
        Выполняет запрос к VK API с троттлингом и повтором при error_code 6
        и сетевых сбоях.
        """

        attempt = 0

        while True:
            await self._throttle()

            try:
                async with httpx.AsyncClient(timeout=self._request_timeout) as client:
                    response = await client.get(
                        f"{self.BASE_URL}/{method}",
                        params=params,
                    )

                response.raise_for_status()
            except httpx.TransportError as exc:
                # Сетевые сбои: таймауты, обрыв соединения, DNS и т.п.
                if attempt < self._max_retries:
                    attempt += 1
                    delay = self._backoff_delay(attempt)

                    logger.warning(
                        "VK %s network error (%s), retry %d/%d after %.2fs",
                        method,
                        type(exc).__name__,
                        attempt,
                        self._max_retries,
                        delay,
                    )

                    await asyncio.sleep(delay)
                    continue

                raise

            data = response.json()

            error = data.get("error")

            if error is None:
                return data["response"]

            error_code = error.get("error_code")

            if error_code == VK_TOO_MANY_REQUESTS and attempt < self._max_retries:
                attempt += 1
                delay = self._backoff_delay(attempt)

                logger.warning(
                    "VK %s rate limited (error_code 6), retry %d/%d after %.2fs",
                    method,
                    attempt,
                    self._max_retries,
                    delay,
                )

                await asyncio.sleep(delay)
                continue

            if error_code == VK_ACCESS_DENIED:
                raise VKAccessDeniedError(
                    owner_id=params.get("owner_id"),
                    error_code=error_code,
                    error_msg=error.get("error_msg", ""),
                )

            raise RuntimeError(error)

    def _backoff_delay(
        self,
        attempt: int,
    ) -> float:

        return self._retry_base_delay * (2 ** (attempt - 1))

    async def _throttle(self) -> None:
        """
        Не даёт слать запросы чаще, чем 1 раз в self._min_interval секунд.

        Пауза выдерживается под локом, поэтому ограничение работает глобально
        для всех конкурентных вызовов одного экземпляра клиента.
        """

        if self._min_interval <= 0:
            return

        async with self._throttle_lock:
            elapsed = time.monotonic() - self._last_request_at
            wait = self._min_interval - elapsed

            if wait > 0:
                await asyncio.sleep(wait)

            self._last_request_at = time.monotonic()
