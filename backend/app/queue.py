from __future__ import annotations

import functools

from redis import Redis
from redis.exceptions import RedisError
from rq import Queue

from .config import settings

QUEUE_NAME = "smbcrawler"


@functools.lru_cache
def get_redis() -> Redis:
    return Redis.from_url(settings.redis_url)


@functools.lru_cache
def get_queue() -> Queue:
    # Crawls are long; give jobs a generous default timeout (24h).
    return Queue(QUEUE_NAME, connection=get_redis(), default_timeout=24 * 3600)


def cancel_key(scan_id: str) -> str:
    return f"scan:{scan_id}:cancel"


def request_cancel(scan_id: str) -> None:
    try:
        get_redis().set(cancel_key(scan_id), "1", ex=24 * 3600)
    except RedisError:
        pass


def cancel_requested(scan_id: str) -> bool:
    try:
        return get_redis().get(cancel_key(scan_id)) is not None
    except RedisError:
        return False


def clear_cancel(scan_id: str) -> None:
    try:
        get_redis().delete(cancel_key(scan_id))
    except RedisError:
        pass
