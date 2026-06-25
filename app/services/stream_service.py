from dataclasses import dataclass
from typing import Any

from redis.exceptions import ResponseError

from app.domain.post import Post
from app.services.post_serializer import deserialize_post
from app.services.post_serializer import serialize_post


@dataclass
class StreamPostMessage:
    stream: str
    message_id: str
    post: Post


class StreamService:
    def __init__(
        self,
        redis_client,
    ) -> None:
        self._redis_client = redis_client

    async def ensure_group(
        self,
        stream: str,
        group: str,
    ) -> None:

        try:
            await self._redis_client.xgroup_create(
                name=stream,
                groupname=group,
                id="0",
                mkstream=True,
            )
        except ResponseError as error:
            if "BUSYGROUP" not in str(error):
                raise

    async def publish_post(
        self,
        stream: str,
        post: Post,
    ) -> str:

        message_id = await self._redis_client.xadd(
            name=stream,
            fields=serialize_post(post),
        )

        return str(message_id)

    async def read_posts(
        self,
        stream: str,
        group: str,
        consumer: str,
        count: int = 10,
        block_ms: int = 5000,
    ) -> list[StreamPostMessage]:

        await self.ensure_group(
            stream=stream,
            group=group,
        )

        response = await self._redis_client.xreadgroup(
            groupname=group,
            consumername=consumer,
            streams={stream: ">"},
            count=count,
            block=block_ms,
        )

        return self._parse_response(response)

    async def claim_stale_posts(
        self,
        stream: str,
        group: str,
        consumer: str,
        count: int = 10,
        min_idle_ms: int = 60000,
    ) -> list[StreamPostMessage]:

        await self.ensure_group(stream=stream, group=group)

        result = await self._redis_client.xautoclaim(
            name=stream,
            groupname=group,
            consumername=consumer,
            min_idle_time=min_idle_ms,
            start_id="0-0",
            count=count,
        )

        claimed = result[1] if isinstance(result, (list, tuple)) and len(result) >= 2 else []

        messages: list[StreamPostMessage] = []
        for message_id, data in claimed:
            if not data:
                continue
            messages.append(
                StreamPostMessage(
                    stream=str(stream),
                    message_id=str(message_id),
                    post=deserialize_post(data),
                )
            )

        return messages

    async def ack(
        self,
        stream: str,
        group: str,
        message_id: str,
    ) -> None:

        await self._redis_client.xack(
            stream,
            group,
            message_id,
        )

    def _parse_response(
        self,
        response: list[Any],
    ) -> list[StreamPostMessage]:

        messages: list[StreamPostMessage] = []

        for stream_name, stream_messages in response:
            for message_id, data in stream_messages:
                messages.append(
                    StreamPostMessage(
                        stream=str(stream_name),
                        message_id=str(message_id),
                        post=deserialize_post(data),
                    )
                )

        return messages
