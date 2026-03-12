import asyncio

from app.core.redis import redis_client


async def main():

    last_id = "0"

    while True:

        messages = await redis_client.xread(
            {"raw_posts": last_id},
            block=0
        )

        for stream_name, stream_messages in messages:

            for message_id, data in stream_messages:

                text = data["text"]

                print("received:", text)

                if len(text) < 30:
                    print("rejected: too short")

                elif "казино" in text.lower():
                    print("rejected: casino")

                elif "курьер" in text.lower():
                    print("rejected: courier")

                else:
                    print("accepted")

                last_id = message_id


asyncio.run(main())