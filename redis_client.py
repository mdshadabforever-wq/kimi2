import time
import redis
from config import Config

_redis_outage_simulated = False
_client = None

class InMemoryRedisMock:
    """In-memory Redis emulator for mock testing where Redis is not running."""
    def __init__(self):
        self.store = {}
        self.expirations = {}

    def ping(self):
        return True

    def set(self, key, value, ex=None):
        self.store[key] = str(value)
        if ex:
            self.expirations[key] = time.time() + ex
        else:
            self.expirations.pop(key, None)
        return True

    def get(self, key):
        # Expiry check
        if key in self.expirations:
            if time.time() > self.expirations[key]:
                self.store.pop(key, None)
                self.expirations.pop(key, None)
                return None
        return self.store.get(key)

    def delete(self, key):
        existed = key in self.store
        self.store.pop(key, None)
        self.expirations.pop(key, None)
        return 1 if existed else 0

def set_redis_outage(status: bool):
    """Toggles Redis outage simulation for health monitoring and Ghost Mode tests."""
    global _redis_outage_simulated
    _redis_outage_simulated = status

def get_client():
    """Returns a Redis client or mock instance, respecting simulated outages."""
    global _redis_outage_simulated, _client
    if _redis_outage_simulated:
        raise redis.ConnectionError("Simulated Redis outage")
    
    if _client is None:
        if Config.MOCK_MODE:
            _client = InMemoryRedisMock()
        else:
            _client = redis.Redis(
                host=Config.REDIS_HOST,
                port=Config.REDIS_PORT,
                decode_responses=True,
                socket_timeout=2.0
            )
    return _client

def ping():
    """Pings the Redis server to check health."""
    if _redis_outage_simulated:
        raise redis.ConnectionError("Simulated Redis outage")
    
    try:
        client = get_client()
        return client.ping()
    except Exception as e:
        raise redis.ConnectionError(f"Redis connection failed: {e}")

def set_val(key, value, ex=None):
    """Sets a value in Redis with optional expiration."""
    if _redis_outage_simulated:
        raise redis.ConnectionError("Simulated Redis outage")
    
    client = get_client()
    return client.set(key, value, ex=ex)

def get_val(key):
    """Gets a value from Redis."""
    if _redis_outage_simulated:
        raise redis.ConnectionError("Simulated Redis outage")
    
    client = get_client()
    return client.get(key)

def delete_val(key):
    """Deletes a key from Redis."""
    if _redis_outage_simulated:
        raise redis.ConnectionError("Simulated Redis outage")
    
    client = get_client()
    return client.delete(key)
