"""Storage layer for FeedbackItems and IssueClusters.

Defaults to in-memory dicts, but will use Redis if configured (Upstash-friendly).
"""

import json
import os
import time
from datetime import datetime
from typing import Dict, Iterable, List, Optional
from uuid import UUID

import requests

from .models import FeedbackItem, IssueCluster

try:
    import redis  # type: ignore
except ImportError:
    redis = None


def _dt_to_iso(dt: datetime) -> str:
    return dt.isoformat()


def _iso_to_dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


# ---------- Redis (standard) client helpers ----------


def _redis_client_from_env():
    """Return a redis-py client if REDIS_URL/UPSTASH_REDIS_URL is set."""
    url = os.getenv("REDIS_URL") or os.getenv("UPSTASH_REDIS_URL")
    if not url or not redis:
        return None
    return redis.from_url(url, decode_responses=True)


# ---------- Upstash REST client (fallback when redis-py URL not provided) ----------


class UpstashRESTClient:
    """Minimal Upstash REST wrapper for the commands we need."""

    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.session = requests.Session()

    def _cmd(self, *args: str):
        resp = self.session.post(
            self.base_url,
            headers={"Authorization": f"Bearer {self.token}"},
            json={"command": list(args)},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("result")

    def set(self, key: str, value: str):
        return self._cmd("SET", key, value)

    def get(self, key: str) -> Optional[str]:
        return self._cmd("GET", key)

    def zadd(self, key: str, score: float, member: str):
        return self._cmd("ZADD", key, str(score), member)

    def zrange(self, key: str, start: int, stop: int, rev: bool = False) -> List[str]:
        args = ["ZRANGE", key, str(start), str(stop)]
        if rev:
            args.append("REV")
        result = self._cmd(*args)
        return result or []

    def sadd(self, key: str, member: str):
        return self._cmd("SADD", key, member)

    def smembers(self, key: str) -> List[str]:
        result = self._cmd("SMEMBERS", key)
        return result or []

    def delete(self, *keys: str):
        if not keys:
            return 0
        return self._cmd("DEL", *keys)

    def scan_iter(self, pattern: str, count: int = 100) -> Iterable[str]:
        cursor = "0"
        while True:
            result = self._cmd("SCAN", cursor, "MATCH", pattern, "COUNT", str(count))
            cursor = result[0]
            for key in result[1]:
                yield key
            if cursor == "0":
                break


def _upstash_rest_client_from_env():
    url = os.getenv("UPSTASH_REDIS_REST_URL")
    token = os.getenv("UPSTASH_REDIS_REST_TOKEN")
    if url and token:
        return UpstashRESTClient(url, token)
    return None


# ---------- Store backends ----------


class InMemoryStore:
    def __init__(self):
        self.feedback_items: Dict[UUID, FeedbackItem] = {}
        self.issue_clusters: Dict[UUID, IssueCluster] = {}
        self.reddit_subreddits: Optional[List[str]] = None

    # Feedback
    def add_feedback_item(self, item: FeedbackItem) -> FeedbackItem:
        self.feedback_items[item.id] = item
        return item

    def get_feedback_item(self, item_id: UUID) -> Optional[FeedbackItem]:
        return self.feedback_items.get(item_id)

    def get_all_feedback_items(self) -> List[FeedbackItem]:
        return list(self.feedback_items.values())

    def clear_feedback_items(self):
        self.feedback_items.clear()

    # Clusters
    def add_cluster(self, cluster: IssueCluster) -> IssueCluster:
        self.issue_clusters[cluster.id] = cluster
        return cluster

    def get_cluster(self, cluster_id: UUID) -> Optional[IssueCluster]:
        return self.issue_clusters.get(cluster_id)

    def get_all_clusters(self) -> List[IssueCluster]:
        return list(self.issue_clusters.values())

    def update_cluster(self, cluster_id: UUID, **updates) -> IssueCluster:
        cluster = self.issue_clusters[cluster_id]
        updated_cluster = cluster.model_copy(update=updates)
        self.issue_clusters[cluster_id] = updated_cluster
        return updated_cluster

    def clear_clusters(self):
        self.issue_clusters.clear()

    # Config (Reddit)
    def set_reddit_subreddits(self, subreddits: List[str]) -> List[str]:
        self.reddit_subreddits = subreddits
        return subreddits

    def get_reddit_subreddits(self) -> Optional[List[str]]:
        return self.reddit_subreddits

    def clear_config(self):
        self.reddit_subreddits = None


class RedisStore:
    """Redis-backed implementation (works with Upstash REST or redis-py)."""

    def __init__(self):
        client = _redis_client_from_env()
        self.mode = "redis" if client else "rest"
        if client:
            self.client = client
        else:
            rest_client = _upstash_rest_client_from_env()
            if not rest_client:
                raise RuntimeError("RedisStore requires REDIS_URL/UPSTASH_REDIS_URL or UPSTASH_REDIS_REST_URL/_TOKEN")
            self.client = rest_client

    # Key helpers
    @staticmethod
    def _feedback_key(item_id: UUID) -> str:
        return f"feedback:{item_id}"

    @staticmethod
    def _feedback_created_key() -> str:
        return "feedback:created"

    @staticmethod
    def _feedback_source_key(source: str) -> str:
        return f"feedback:source:{source}"

    @staticmethod
    def _feedback_external_key(source: str, external_id: str) -> str:
        return f"feedback:external:{source}:{external_id}"

    @staticmethod
    def _cluster_key(cluster_id: UUID) -> str:
        return f"cluster:{cluster_id}"

    @staticmethod
    def _cluster_items_key(cluster_id: UUID) -> str:
        return f"cluster:items:{cluster_id}"

    @staticmethod
    def _cluster_all_key() -> str:
        return "clusters:all"

    @staticmethod
    def _reddit_subreddits_key() -> str:
        return "config:reddit:subreddits"

    # Feedback
    def add_feedback_item(self, item: FeedbackItem) -> FeedbackItem:
        payload = item.model_dump()
        if isinstance(payload["created_at"], datetime):
            payload["created_at"] = _dt_to_iso(payload["created_at"])

        serialized = json.dumps(payload)
        key = self._feedback_key(item.id)
        self._set(key, serialized)

        ts = item.created_at.timestamp() if isinstance(item.created_at, datetime) else time.time()
        self._zadd(self._feedback_created_key(), ts, str(item.id))
        self._zadd(self._feedback_source_key(item.source), ts, str(item.id))
        if item.external_id:
            self._set(self._feedback_external_key(item.source, item.external_id), str(item.id))
        return item

    def get_feedback_item(self, item_id: UUID) -> Optional[FeedbackItem]:
        raw = self._get(self._feedback_key(item_id))
        if not raw:
            return None
        data = json.loads(raw)
        if isinstance(data.get("created_at"), str):
            data["created_at"] = _iso_to_dt(data["created_at"])
        return FeedbackItem(**data)

    def get_all_feedback_items(self) -> List[FeedbackItem]:
        ids = self._zrange(self._feedback_created_key(), 0, -1)
        items: List[FeedbackItem] = []
        for item_id in ids:
            item = self.get_feedback_item(UUID(item_id))
            if item:
                items.append(item)
        return items

    def clear_feedback_items(self):
        # Remove keys matching feedback:* and related sorted sets
        feedback_keys = list(self._scan_iter("feedback:*"))
        if feedback_keys:
            self._delete(*feedback_keys)
        self._delete(self._feedback_created_key())
        # Source sets: optional to scan
        source_keys = list(self._scan_iter("feedback:source:*"))
        if source_keys:
            self._delete(*source_keys)

    # Clusters
    def add_cluster(self, cluster: IssueCluster) -> IssueCluster:
        payload = cluster.model_dump()
        for field in ("created_at", "updated_at"):
            if isinstance(payload.get(field), datetime):
                payload[field] = _dt_to_iso(payload[field])
        serialized = json.dumps(payload)
        key = self._cluster_key(cluster.id)
        self._set(key, serialized)
        self._sadd(self._cluster_all_key(), str(cluster.id))
        # store cluster items set
        items_key = self._cluster_items_key(cluster.id)
        for fid in cluster.feedback_ids:
            self._sadd(items_key, str(fid))
        return cluster

    def get_cluster(self, cluster_id: UUID) -> Optional[IssueCluster]:
        raw = self._get(self._cluster_key(cluster_id))
        if not raw:
            return None
        data = json.loads(raw)
        for field in ("created_at", "updated_at"):
            if isinstance(data.get(field), str):
                data[field] = _iso_to_dt(data[field])
        # feedback_ids stored as strings; ensure UUID conversion handled by Pydantic
        return IssueCluster(**data)

    def get_all_clusters(self) -> List[IssueCluster]:
        ids = self._smembers(self._cluster_all_key())
        clusters: List[IssueCluster] = []
        for cid in ids:
            cluster = self.get_cluster(UUID(cid))
            if cluster:
                clusters.append(cluster)
        return clusters

    def update_cluster(self, cluster_id: UUID, **updates) -> IssueCluster:
        cluster = self.get_cluster(cluster_id)
        if not cluster:
            raise KeyError(f"Cluster {cluster_id} not found")
        updated = cluster.model_copy(update=updates)
        return self.add_cluster(updated)

    def clear_clusters(self):
        cluster_keys = list(self._scan_iter("cluster:*")) + [self._cluster_all_key()]
        if cluster_keys:
            self._delete(*cluster_keys)

    # Config (Reddit)
    def set_reddit_subreddits(self, subreddits: List[str]) -> List[str]:
        payload = json.dumps(subreddits)
        self._set(self._reddit_subreddits_key(), payload)
        return subreddits

    def get_reddit_subreddits(self) -> Optional[List[str]]:
        raw = self._get(self._reddit_subreddits_key())
        if not raw:
            return None
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return [str(s) for s in data]
        except json.JSONDecodeError:
            return None
        return None

    def clear_config(self):
        self._delete(self._reddit_subreddits_key())

    # --- client wrappers ---
    def _set(self, key: str, value: str):
        if self.mode == "redis":
            self.client.set(key, value)
        else:
            self.client.set(key, value)

    def _get(self, key: str) -> Optional[str]:
        return self.client.get(key)

    def _zadd(self, key: str, score: float, member: str):
        if self.mode == "redis":
            self.client.zadd(key, {member: score})
        else:
            self.client.zadd(key, score, member)

    def _zrange(self, key: str, start: int, stop: int, rev: bool = False) -> List[str]:
        if self.mode == "redis":
            return self.client.zrange(key, start, stop, desc=rev)
        return self.client.zrange(key, start, stop, rev=rev)

    def _sadd(self, key: str, member: str):
        if self.mode == "redis":
            self.client.sadd(key, member)
        else:
            self.client.sadd(key, member)

    def _smembers(self, key: str) -> List[str]:
        if self.mode == "redis":
            return list(self.client.smembers(key))
        return self.client.smembers(key)

    def _delete(self, *keys: str):
        if not keys:
            return
        if self.mode == "redis":
            self.client.delete(*keys)
        else:
            self.client.delete(*keys)

    def _scan_iter(self, pattern: str) -> Iterable[str]:
        if self.mode == "redis":
            yield from self.client.scan_iter(pattern)
        else:
            yield from self.client.scan_iter(pattern)


# ---------- Store selector ----------


def _select_store():
    try:
        if os.getenv("REDIS_URL") or os.getenv("UPSTASH_REDIS_URL") or os.getenv("UPSTASH_REDIS_REST_URL"):
            return RedisStore()
    except Exception as exc:  # fall back silently for local dev if misconfigured
        print(f"RedisStore unavailable, falling back to in-memory. Reason: {exc}")
    return InMemoryStore()


_STORE = _select_store()


# Public API (delegates to current store)
def add_feedback_item(item: FeedbackItem) -> FeedbackItem:
    return _STORE.add_feedback_item(item)


def get_feedback_item(item_id: UUID) -> Optional[FeedbackItem]:
    return _STORE.get_feedback_item(item_id)


def get_all_feedback_items() -> List[FeedbackItem]:
    return _STORE.get_all_feedback_items()


def clear_feedback_items():
    _STORE.clear_feedback_items()


def add_cluster(cluster: IssueCluster) -> IssueCluster:
    return _STORE.add_cluster(cluster)


def get_cluster(cluster_id: UUID) -> Optional[IssueCluster]:
    return _STORE.get_cluster(cluster_id)


def get_all_clusters() -> List[IssueCluster]:
    return _STORE.get_all_clusters()


def update_cluster(cluster_id: UUID, **updates) -> IssueCluster:
    return _STORE.update_cluster(cluster_id, **updates)


def clear_clusters():
    _STORE.clear_clusters()


def set_reddit_subreddits(subreddits: List[str]) -> List[str]:
    return _STORE.set_reddit_subreddits(subreddits)


def get_reddit_subreddits() -> Optional[List[str]]:
    return _STORE.get_reddit_subreddits()


def clear_config():
    # Primarily for tests
    if hasattr(_STORE, "clear_config"):
        _STORE.clear_config()
