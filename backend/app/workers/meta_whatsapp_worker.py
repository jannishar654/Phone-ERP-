import asyncio
import logging

from app.services.meta_whatsapp_event_service import meta_whatsapp_event_service


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


def main() -> None:
    asyncio.run(meta_whatsapp_event_service.run_worker_forever())


if __name__ == "__main__":
    main()
