from __future__ import annotations

"""
RQ Worker entrypoint.
Run with: python -m app.workers.worker
"""

import os

import redis
from rq import Worker, Queue, Connection

from app.core.config import settings
from app.core.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


def main() -> None:
    conn = redis.from_url(settings.REDIS_URL)
    queue_names = [settings.RQ_QUEUE_NAME, "default"]

    logger.info("worker_starting", queues=queue_names, redis=settings.REDIS_URL)

    with Connection(conn):
        worker = Worker(
            queues=[Queue(name, connection=conn) for name in queue_names],
            connection=conn,
        )
        worker.work(with_scheduler=True)


if __name__ == "__main__":
    main()
