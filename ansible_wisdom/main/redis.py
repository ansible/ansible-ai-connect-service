#!/usr/bin/env python3

import redis.exceptions
from django.core.cache.backends.redis import RedisCache, RedisCacheClient
from redis import RedisCluster


class RedisClusterCacheClient(RedisCacheClient):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._client = RedisCluster

    def get_client(self, key=None, *, write=False):
        for server in self._servers:
            try:
                return self._client.from_url(server)
            except redis.exceptions.RedisClusterException:
                continue


class CustomRedisCluster(RedisCache):
    """Redis client for Django based on RedisCluster

    This driver only works with the Redis Clusters. Use
    "django.core.cache.backends.redis.RedisCache" for the
    regular deployment.
    """

    def __init__(self, server, params):
        super().__init__(server, params)
        self._class = RedisClusterCacheClient
