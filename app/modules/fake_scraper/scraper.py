import asyncio

from app.core.redis import redis_client


async def main():

    while True:

        fake_post = {
            "source": "tg",
            "text": "На сейчас нужен грузчик 500/2"
        }

        await redis_client.xadd(
            "raw_posts",
            fake_post
        )

        print("post added")

        await asyncio.sleep(5)


asyncio.run(main())