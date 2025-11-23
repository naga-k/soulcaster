import pytest
from unittest.mock import patch
from backend.store import InMemoryStore

@pytest.fixture(scope="session", autouse=True)
def mock_store():
    """
    Force the use of InMemoryStore for all tests, ignoring Redis configuration.
    This ensures tests don't try to connect to a real Redis/Upstash instance
    and fail due to missing/invalid credentials or network issues.
    """
    # Create a fresh InMemoryStore
    memory_store = InMemoryStore()
    
    # Patch the _STORE global in backend.store
    with patch("backend.store._STORE", memory_store):
        yield memory_store
