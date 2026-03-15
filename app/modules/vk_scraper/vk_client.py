# app/modules/vk_scraper/vk_client.py


class VKClient:
    """
    Клиент для работы с VK API.

    На текущем этапе это только интерфейс.
    Реальная работа с API будет добавлена позже.
    """

    async def get_latest_posts(
        self,
        owner_id: int,
        count: int = 20,
    ) -> list[dict]:
        """
        Получить последние посты сообщества.

        Parameters
        ----------
        owner_id
            ID сообщества.

        count
            Сколько постов получить.

        Returns
        -------
        list[dict]
            Список постов VK API.
        """

        raise NotImplementedError

    async def get_group_info(
        self,
        owner_id: int,
    ) -> dict:
        """
        Получить информацию о сообществе.

        Parameters
        ----------
        owner_id
            ID сообщества.

        Returns
        -------
        dict
            Данные сообщества.
        """

        raise NotImplementedError