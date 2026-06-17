import pytest
import redis
import redis_client

def test_redis_operations():
    """Verify standard Redis connection and cache operations (SET, GET, DELETE)."""
    # Ping
    assert redis_client.ping() is True
    
    # Set & Get
    redis_client.set_val("test_key", "test_value", ex=60)
    assert redis_client.get_val("test_key") == "test_value"
    
    # Delete
    redis_client.delete_val("test_key")
    assert redis_client.get_val("test_key") is None

def test_redis_outage_simulation():
    """Verify simulated Redis outage blocks operations."""
    redis_client.set_redis_outage(True)
    
    with pytest.raises(redis.ConnectionError) as excinfo:
        redis_client.ping()
    assert "Simulated Redis outage" in str(excinfo.value)
    
    with pytest.raises(redis.ConnectionError) as excinfo:
        redis_client.set_val("key", "val")
    assert "Simulated Redis outage" in str(excinfo.value)
    
    # Restore
    redis_client.set_redis_outage(False)
    assert redis_client.ping() is True
