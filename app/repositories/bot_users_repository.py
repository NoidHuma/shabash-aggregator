from sqlalchemy import select


class BotUsersRepository:
    """Репозиторий пользователей бота. Параметризуется моделью (TG/VK)."""

    def __init__(self, model) -> None:
        self._model = model

    async def get_by_external_id(self, session, external_id: int):
        stmt = select(self._model).where(self._model.external_id == external_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def add(self, session, user):
        session.add(user)
        await session.flush()
        return user

    async def list_active(self, session) -> list:
        stmt = select(self._model).where(self._model.status == "active")
        result = await session.execute(stmt)
        return list(result.scalars().all())
