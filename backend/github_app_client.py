"""GitHub App integration helpers.

This module provides utilities for GitHub App authentication and webhook processing:
- JWT generation for GitHub App authentication
- Installation access token management with Redis caching
- Webhook signature verification (HMAC-SHA256)
- GitHub API calls with installation tokens
"""

import hashlib
import hmac
import json
import logging
import os
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

import jwt
import requests

logger = logging.getLogger(__name__)


def _get_redis_client():
    """Get Redis client for caching (redis-py or Upstash REST)."""
    from store import _redis_client_from_env, _upstash_rest_client_from_env

    client = _redis_client_from_env()
    if client:
        return client
    return _upstash_rest_client_from_env()


def verify_github_webhook_signature(body: bytes, signature: str, secret: str) -> bool:
    """
    Verify GitHub webhook signature using HMAC-SHA256.

    GitHub signs webhook payloads and sends the signature in the
    'X-Hub-Signature-256' header as 'sha256=<hash>'.

    Parameters:
        body (bytes): Raw request body bytes (before JSON parsing).
        signature (str): Signature from the 'X-Hub-Signature-256' header.
        secret (str): GitHub App webhook secret configured in GitHub settings.

    Returns:
        bool: True if signature is valid, False otherwise.
    """
    if not signature or not secret:
        return False

    try:
        # Extract hash from "sha256=<hash>" format
        sig_type, sig_hash = signature.split("=", 1)
        if sig_type != "sha256":
            logger.warning(f"Unexpected signature type: {sig_type}, expected sha256")
            return False

        expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(sig_hash, expected)
    except Exception as e:
        logger.warning(f"Webhook signature verification failed: {e}")
        return False


def generate_jwt() -> str:
    """
    Generate GitHub App JWT for authentication.

    GitHub Apps authenticate using a JWT signed with their private key.
    The JWT is valid for 10 minutes and used to request installation access tokens.

    Returns:
        str: Signed JWT token.

    Raises:
        RuntimeError: If GITHUB_APP_ID or GITHUB_APP_PRIVATE_KEY is not set.
    """
    app_id = os.getenv("GITHUB_APP_ID")
    private_key = os.getenv("GITHUB_APP_PRIVATE_KEY")

    if not app_id:
        raise RuntimeError("GITHUB_APP_ID environment variable is required")
    if not private_key:
        raise RuntimeError("GITHUB_APP_PRIVATE_KEY environment variable is required")

    # Handle escaped newlines in private key
    private_key = private_key.replace("\\n", "\n")

    now = int(time.time())
    payload = {
        "iat": now,  # Issued at time
        "exp": now + 600,  # Expires in 10 minutes
        "iss": app_id  # Issuer (GitHub App ID)
    }

    return jwt.encode(payload, private_key, algorithm="RS256")


def get_installation_access_token(installation_id: int, force_refresh: bool = False) -> str:
    """
    Get installation access token (cached in Redis).

    Installation tokens are valid for 1 hour. This function caches them in Redis
    with a 55-minute TTL (5-minute buffer) to avoid using expired tokens.

    Parameters:
        installation_id (int): GitHub installation ID.
        force_refresh (bool): If True, bypass cache and fetch new token.

    Returns:
        str: Installation access token.

    Raises:
        RuntimeError: If unable to get token from GitHub.
    """
    cache_key = f"github:app:installation:{installation_id}:token"
    redis_client = _get_redis_client()

    # Check Redis cache first (unless force refresh)
    if not force_refresh and redis_client:
        try:
            cached = redis_client.hgetall(cache_key)
            if cached and cached.get("expires_at"):
                expires_at = datetime.fromisoformat(cached["expires_at"])
                if expires_at > datetime.now(timezone.utc):
                    logger.debug(f"Using cached installation token for {installation_id}")
                    return cached["token"]
        except Exception as e:
            logger.warning(f"Error reading cached token: {e}")

    # Generate new token from GitHub
    logger.info(f"Fetching new installation token for {installation_id}")
    jwt_token = generate_jwt()

    response = requests.post(
        f"https://api.github.com/app/installations/{installation_id}/access_tokens",
        headers={
            "Authorization": f"Bearer {jwt_token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "Soulcaster/1.0"
        },
        timeout=10
    )

    if response.status_code != 201:
        logger.error(f"Failed to get installation token: {response.status_code} {response.text}")
        raise RuntimeError(f"Failed to get installation token: {response.status_code}")

    data = response.json()
    token = data["token"]
    expires_at = data["expires_at"]

    # Cache with 55-minute TTL (5-min buffer before 1h expiry)
    if redis_client:
        try:
            redis_client.hset(cache_key, "token", token)
            redis_client.hset(cache_key, "expires_at", expires_at)
            redis_client.expire(cache_key, 3300)  # 55 minutes
            logger.debug(f"Cached installation token for {installation_id} until {expires_at}")
        except Exception as e:
            logger.warning(f"Error caching token: {e}")

    return token


def get_installation_details(installation_id: int) -> Dict:
    """
    Fetch installation details from GitHub.

    Parameters:
        installation_id (int): GitHub installation ID.

    Returns:
        dict: Installation data including account, permissions, repositories, etc.
    """
    token = get_installation_access_token(installation_id)

    response = requests.get(
        f"https://api.github.com/app/installations/{installation_id}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "Soulcaster/1.0"
        },
        timeout=10
    )

    response.raise_for_status()
    return response.json()


def get_installation_repos(installation_id: int) -> List[Dict]:
    """
    Fetch repositories for an installation.

    Parameters:
        installation_id (int): GitHub installation ID.

    Returns:
        list: List of repository dicts with id, full_name, private, etc.
    """
    token = get_installation_access_token(installation_id)

    response = requests.get(
        f"https://api.github.com/installation/repositories",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "Soulcaster/1.0"
        },
        timeout=10
    )

    response.raise_for_status()
    data = response.json()
    return data.get("repositories", [])


def fetch_repo_issues_with_installation_token(
    installation_id: int,
    owner: str,
    repo: str,
    state: str = "open",
    since: Optional[str] = None,
    max_pages: int = 20,
    max_issues: int = 2000
) -> List[Dict]:
    """
    Fetch repository issues using installation token.

    Similar to fetch_repo_issues() in github_client.py but uses installation token.

    Parameters:
        installation_id (int): GitHub installation ID.
        owner (str): Repository owner (org or user).
        repo (str): Repository name.
        state (str): Issue state filter: "open", "closed", or "all".
        since (Optional[str]): ISO 8601 timestamp to fetch issues updated after.
        max_pages (int): Maximum pages to fetch (default 20).
        max_issues (int): Maximum issues to fetch (default 2000).

    Returns:
        list: List of issue dicts from GitHub API.
    """
    token = get_installation_access_token(installation_id)

    issues = []
    page = 1
    per_page = 100

    while len(issues) < max_issues and page <= max_pages:
        params = {
            "state": state,
            "sort": "updated",
            "direction": "desc",
            "per_page": per_page,
            "page": page
        }
        if since:
            params["since"] = since

        response = requests.get(
            f"https://api.github.com/repos/{owner}/{repo}/issues",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "User-Agent": "Soulcaster/1.0"
            },
            params=params,
            timeout=30
        )

        response.raise_for_status()
        page_issues = response.json()

        if not page_issues:
            break

        # Filter out pull requests (they appear in issues endpoint)
        page_issues = [issue for issue in page_issues if not issue.get("pull_request")]

        issues.extend(page_issues)

        # Check if there's another page
        link_header = response.headers.get("Link", "")
        if 'rel="next"' not in link_header:
            break

        page += 1

    return issues[:max_issues]


def get_rate_limit_status(installation_id: int) -> Dict:
    """
    Get GitHub API rate limit status for an installation.

    Parameters:
        installation_id (int): GitHub installation ID.

    Returns:
        dict: Rate limit data with remaining requests, limit, reset time.
    """
    token = get_installation_access_token(installation_id)

    response = requests.get(
        "https://api.github.com/rate_limit",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "Soulcaster/1.0"
        },
        timeout=10
    )

    response.raise_for_status()
    return response.json()
