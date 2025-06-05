"""
Redis Client Module
Handles Redis connections and operations for the logging server.
"""

import os
import json
import redis
from typing import Optional, Dict, List, Any
from loguru import logger

class RedisClient:
    """Redis client for caching and real-time data storage."""
    
    def __init__(self):
        """Initialize Redis client with configuration from environment."""
        self.host = os.environ.get('REDIS_HOST', '127.0.0.1')
        self.port = int(os.environ.get('REDIS_PORT', 6379))
        self.db = int(os.environ.get('REDIS_DB', 0))
        self.password = os.environ.get('REDIS_PASSWORD', None)
        
        self.client = None
        self.connect()
    
    def connect(self) -> bool:
        """Establish connection to Redis server."""
        try:
            self.client = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30
            )
            
            # Test connection
            self.client.ping()
            logger.info(f"✅ Connected to Redis at {self.host}:{self.port}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to Redis: {e}")
            self.client = None
            return False
    
    def ping(self) -> bool:
        """Check if Redis connection is alive."""
        try:
            if self.client:
                self.client.ping()
                return True
        except Exception as e:
            logger.warning(f"Redis ping failed: {e}")
        return False
    
    def set(self, key: str, value: Any, expire: Optional[int] = None) -> bool:
        """Set a key-value pair in Redis."""
        try:
            if not self.client:
                return False
            
            # Serialize complex objects to JSON
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            
            result = self.client.set(key, value, ex=expire)
            return bool(result)
            
        except Exception as e:
            logger.error(f"Redis SET failed for key '{key}': {e}")
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from Redis by key."""
        try:
            if not self.client:
                return default
            
            value = self.client.get(key)
            if value is None:
                return default
            
            # Try to deserialize JSON
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
                
        except Exception as e:
            logger.error(f"Redis GET failed for key '{key}': {e}")
            return default
    
    def delete(self, *keys: str) -> int:
        """Delete one or more keys from Redis."""
        try:
            if not self.client or not keys:
                return 0
            
            return self.client.delete(*keys)
            
        except Exception as e:
            logger.error(f"Redis DELETE failed for keys {keys}: {e}")
            return 0
    
    def exists(self, key: str) -> bool:
        """Check if a key exists in Redis."""
        try:
            if not self.client:
                return False
            
            return bool(self.client.exists(key))
            
        except Exception as e:
            logger.error(f"Redis EXISTS failed for key '{key}': {e}")
            return False
    
    def incr(self, key: str, amount: int = 1) -> Optional[int]:
        """Increment a numeric value in Redis."""
        try:
            if not self.client:
                return None
            
            return self.client.incr(key, amount)
            
        except Exception as e:
            logger.error(f"Redis INCR failed for key '{key}': {e}")
            return None
    
    def expire(self, key: str, seconds: int) -> bool:
        """Set expiration time for a key."""
        try:
            if not self.client:
                return False
            
            return bool(self.client.expire(key, seconds))
            
        except Exception as e:
            logger.error(f"Redis EXPIRE failed for key '{key}': {e}")
            return False
    
    def lpush(self, key: str, *values: Any) -> Optional[int]:
        """Push values to the left of a list."""
        try:
            if not self.client:
                return None
            
            # Serialize complex objects
            serialized_values = []
            for value in values:
                if isinstance(value, (dict, list)):
                    serialized_values.append(json.dumps(value))
                else:
                    serialized_values.append(value)
            
            return self.client.lpush(key, *serialized_values)
            
        except Exception as e:
            logger.error(f"Redis LPUSH failed for key '{key}': {e}")
            return None
    
    def lrange(self, key: str, start: int = 0, end: int = -1) -> List[Any]:
        """Get a range of elements from a list."""
        try:
            if not self.client:
                return []
            
            values = self.client.lrange(key, start, end)
            
            # Try to deserialize JSON values
            result = []
            for value in values:
                try:
                    result.append(json.loads(value))
                except (json.JSONDecodeError, TypeError):
                    result.append(value)
            
            return result
            
        except Exception as e:
            logger.error(f"Redis LRANGE failed for key '{key}': {e}")
            return []
    
    def ltrim(self, key: str, start: int, end: int) -> bool:
        """Trim a list to the specified range."""
        try:
            if not self.client:
                return False
            
            return bool(self.client.ltrim(key, start, end))
            
        except Exception as e:
            logger.error(f"Redis LTRIM failed for key '{key}': {e}")
            return False
    
    def hset(self, key: str, field: str, value: Any) -> bool:
        """Set a field in a hash."""
        try:
            if not self.client:
                return False
            
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            
            return bool(self.client.hset(key, field, value))
            
        except Exception as e:
            logger.error(f"Redis HSET failed for key '{key}', field '{field}': {e}")
            return False
    
    def hget(self, key: str, field: str, default: Any = None) -> Any:
        """Get a field from a hash."""
        try:
            if not self.client:
                return default
            
            value = self.client.hget(key, field)
            if value is None:
                return default
            
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
                
        except Exception as e:
            logger.error(f"Redis HGET failed for key '{key}', field '{field}': {e}")
            return default
    
    def hgetall(self, key: str) -> Dict[str, Any]:
        """Get all fields and values from a hash."""
        try:
            if not self.client:
                return {}
            
            hash_data = self.client.hgetall(key)
            
            # Try to deserialize JSON values
            result = {}
            for field, value in hash_data.items():
                try:
                    result[field] = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    result[field] = value
            
            return result
            
        except Exception as e:
            logger.error(f"Redis HGETALL failed for key '{key}': {e}")
            return {}
    
    def publish(self, channel: str, message: Any) -> Optional[int]:
        """Publish a message to a Redis channel."""
        try:
            if not self.client:
                return None
            
            if isinstance(message, (dict, list)):
                message = json.dumps(message)
            
            return self.client.publish(channel, message)
            
        except Exception as e:
            logger.error(f"Redis PUBLISH failed for channel '{channel}': {e}")
            return None
    
    def get_info(self) -> Dict[str, Any]:
        """Get Redis server information."""
        try:
            if not self.client:
                return {}
            
            return self.client.info()
            
        except Exception as e:
            logger.error(f"Redis INFO failed: {e}")
            return {}
    
    def flushdb(self) -> bool:
        """Flush the current database (use with caution!)."""
        try:
            if not self.client:
                return False
            
            self.client.flushdb()
            logger.warning("Redis database flushed")
            return True
            
        except Exception as e:
            logger.error(f"Redis FLUSHDB failed: {e}")
            return False
    
    def close(self):
        """Close the Redis connection."""
        try:
            if self.client:
                self.client.close()
                logger.info("Redis connection closed")
        except Exception as e:
            logger.error(f"Error closing Redis connection: {e}")
    
    def __del__(self):
        """Cleanup when object is destroyed."""
        self.close()
