import os

from fastapi.testclient import TestClient

from backend.main import app
from backend.store import clear_config

client = TestClient(app)


def setup_function():
    clear_config()
    for key in ("REDDIT_SUBREDDITS", "REDDIT_SUBREDDIT"):
        os.environ.pop(key, None)


def test_get_config_uses_env_when_no_store():
    os.environ["REDDIT_SUBREDDITS"] = "Foo, Bar"

    response = client.get("/config/reddit/subreddits")

    assert response.status_code == 200
    assert response.json()["subreddits"] == ["foo", "bar"]


def test_set_config_persists_and_dedupes():
    response = client.post(
        "/config/reddit/subreddits",
        json={"subreddits": [" Test ", "test", "other"]},
    )

    assert response.status_code == 200
    assert response.json()["subreddits"] == ["test", "other"]

    # Should read back from store, not env
    os.environ["REDDIT_SUBREDDITS"] = "ignored"
    read_back = client.get("/config/reddit/subreddits")
    assert read_back.json()["subreddits"] == ["test", "other"]


def test_set_config_requires_non_empty_list():
    response = client.post(
        "/config/reddit/subreddits",
        json={"subreddits": [" ", ""]},
    )
    assert response.status_code == 400
