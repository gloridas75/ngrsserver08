"""
Redis Connection Manager
Provides singleton Redis client with connection pooling
"""
import os
import redis
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class RedisConnectionManager:
    """
    Singleton Redis connection manager
    Provides connection pooling and error handling
    """
    
    _instance: Optional['RedisConnectionManager'] = None
    _client: Optional[redis.Redis] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._client is None:
            self._connect()
    
    def _connect(self):
        """Initialize Redis connection"""
        redis_host = os.getenv('REDIS_HOST', 'localhost')
        redis_port = int(os.getenv('REDIS_PORT', '6379'))
        redis_db = int(os.getenv('REDIS_DB', '0'))
        redis_password = os.getenv('REDIS_PASSWORD', None)
        
        # Connection pool settings
        max_connections = int(os.getenv('REDIS_MAX_CONNECTIONS', '10'))
        socket_timeout = float(os.getenv('REDIS_SOCKET_TIMEOUT', '5.0'))
        socket_connect_timeout = float(os.getenv('REDIS_CONNECT_TIMEOUT', '5.0'))
        
        try:
            pool = redis.ConnectionPool(
                host=redis_host,
                port=redis_port,
                db=redis_db,
                password=redis_password,
                max_connections=max_connections,
                socket_timeout=socket_timeout,
                socket_connect_timeout=socket_connect_timeout,
                decode_responses=True  # Auto-decode bytes to strings
            )
            
            self._client = redis.Redis(connection_pool=pool)
            
            # Test connection
            self._client.ping()
            
            logger.info(
                f"Redis connected: {redis_host}:{redis_port} (db={redis_db})"
            )
            
        except redis.ConnectionError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise ConnectionError(
                f"Redis connection failed. Is Redis running on {redis_host}:{redis_port}? "
                f"Error: {e}"
            )
        except Exception as e:
            logger.error(f"Redis initialization error: {e}")
            raise
    
    @property
    def client(self) -> redis.Redis:
        """Get Redis client instance"""
        if self._client is None:
            self._connect()
        return self._client
    
    def ping(self) -> bool:
        """Check if Redis connection is alive"""
        try:
            return self._client.ping()
        except Exception as e:
            logger.warning(f"Redis ping failed: {e}")
            return False
    
    def close(self):
        """Close Redis connection"""
        if self._client:
            self._client.close()
            self._client = None
            logger.info("Redis connection closed")
    
    def flushdb(self):
        """Flush current database (use with caution!)"""
        if self._client:
            self._client.flushdb()
            logger.warning("Redis database flushed")


def get_redis_client() -> redis.Redis:
    """
    Get Redis client instance
    
    Returns:
        redis.Redis: Connected Redis client
    """
    manager = RedisConnectionManager()
    return manager.client
