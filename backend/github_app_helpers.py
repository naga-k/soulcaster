"""GitHub App helper functions for backend.

This module provides helper functions for GitHub App installation management:
- Installation to project ID mapping (via Redis cache)
- Repository enablement checking
- Installation cleanup

The dashboard is responsible for keeping Redis in sync with Prisma database
when installations are created, updated, or deleted.
"""

import logging
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)


def _get_redis_client():
    """Get Redis client for querying installation data."""
    from store import _redis_client_from_env, _upstash_rest_client_from_env

    client = _redis_client_from_env()
    if client:
        return client
    return _upstash_rest_client_from_env()


def get_project_id_for_installation(installation_id: int) -> Optional[str]:
    """
    Get project_id for a GitHub App installation.

    This queries Redis for the cached installation mapping. The dashboard
    is responsible for keeping this cache in sync with Prisma.

    Redis key: github:app:installation:{installation_id}:project

    Parameters:
        installation_id (int): GitHub installation ID.

    Returns:
        Optional[str]: Project ID (UUID/CUID) if installation exists, None otherwise.
    """
    redis_client = _get_redis_client()
    if not redis_client:
        logger.warning("Redis client not available for installation lookup")
        return None

    cache_key = f"github:app:installation:{installation_id}:project"

    try:
        project_id = redis_client.get(cache_key)
        if project_id:
            logger.debug(f"Found project {project_id} for installation {installation_id}")
            return project_id
        else:
            logger.warning(f"No project mapping found for installation {installation_id}")
            return None
    except Exception as e:
        logger.error(f"Error looking up installation {installation_id}: {e}")
        return None


def is_repo_enabled_for_project(project_id: str, repository_id: int) -> bool:
    """
    Check if a repository is enabled for webhook sync in a project.

    This queries Redis for the cached repo enablement status. The dashboard
    is responsible for keeping this cache in sync with Prisma.

    Redis key: github:app:repo:{repository_id}:enabled

    Parameters:
        project_id (str): Project ID (for logging, not used in lookup).
        repository_id (int): GitHub repository ID.

    Returns:
        bool: True if repo is enabled, False otherwise.
    """
    redis_client = _get_redis_client()
    if not redis_client:
        logger.warning("Redis client not available for repo enablement check")
        return False  # Default to disabled if can't check

    cache_key = f"github:app:repo:{repository_id}:enabled"

    try:
        enabled = redis_client.get(cache_key)
        # Redis stores "1" for true, "0" for false, or None if not set
        if enabled == "1" or enabled == 1 or enabled == True or enabled == "true":
            return True
        elif enabled == "0" or enabled == 0 or enabled == False or enabled == "false":
            return False
        else:
            # Not in cache - default to enabled for new repos
            logger.debug(f"Repo {repository_id} not in cache, defaulting to enabled")
            return True
    except Exception as e:
        logger.error(f"Error checking repo {repository_id} enablement: {e}")
        return True  # Default to enabled on error


def set_installation_project_mapping(installation_id: int, project_id: str):
    """
    Set the project ID for an installation in Redis cache.

    Called by the dashboard when an installation is created or updated.

    Parameters:
        installation_id (int): GitHub installation ID.
        project_id (str): Project ID (UUID/CUID).
    """
    redis_client = _get_redis_client()
    if not redis_client:
        logger.warning("Redis client not available to set installation mapping")
        return

    cache_key = f"github:app:installation:{installation_id}:project"

    try:
        redis_client.set(cache_key, project_id)
        logger.info(f"Set installation {installation_id} -> project {project_id}")
    except Exception as e:
        logger.error(f"Error setting installation mapping: {e}")


def set_repo_enabled_status(repository_id: int, enabled: bool):
    """
    Set the enabled status for a repository in Redis cache.

    Called by the dashboard when repo enablement is toggled.

    Parameters:
        repository_id (int): GitHub repository ID.
        enabled (bool): Whether the repo is enabled for sync.
    """
    redis_client = _get_redis_client()
    if not redis_client:
        logger.warning("Redis client not available to set repo status")
        return

    cache_key = f"github:app:repo:{repository_id}:enabled"

    try:
        value = "1" if enabled else "0"
        redis_client.set(cache_key, value)
        logger.info(f"Set repo {repository_id} enabled={enabled}")
    except Exception as e:
        logger.error(f"Error setting repo status: {e}")


def cleanup_installation(installation_id: int):
    """
    Clean up Redis cache for a deleted installation.

    Called when a GitHub App installation is deleted.

    Parameters:
        installation_id (int): GitHub installation ID to clean up.
    """
    redis_client = _get_redis_client()
    if not redis_client:
        logger.warning("Redis client not available for cleanup")
        return

    try:
        # Delete installation -> project mapping
        cache_key = f"github:app:installation:{installation_id}:project"
        redis_client.delete(cache_key)

        # Delete cached installation token
        token_key = f"github:app:installation:{installation_id}:token"
        redis_client.delete(token_key)

        logger.info(f"Cleaned up installation {installation_id} from Redis")
    except Exception as e:
        logger.error(f"Error cleaning up installation {installation_id}: {e}")


def cleanup_repo(repository_id: int):
    """
    Clean up Redis cache for a removed repository.

    Called when a repository is removed from an installation.

    Parameters:
        repository_id (int): GitHub repository ID to clean up.
    """
    redis_client = _get_redis_client()
    if not redis_client:
        logger.warning("Redis client not available for cleanup")
        return

    try:
        cache_key = f"github:app:repo:{repository_id}:enabled"
        redis_client.delete(cache_key)

        logger.info(f"Cleaned up repo {repository_id} from Redis")
    except Exception as e:
        logger.error(f"Error cleaning up repo {repository_id}: {e}")


def get_all_installation_mappings() -> Dict[int, str]:
    """
    Get all installation ID -> project ID mappings from Redis.

    Useful for debugging and admin operations.

    Returns:
        dict: Mapping of installation_id (int) -> project_id (str).
    """
    redis_client = _get_redis_client()
    if not redis_client:
        return {}

    try:
        # Scan for all installation keys
        pattern = "github:app:installation:*:project"
        mappings = {}

        if hasattr(redis_client, 'scan_iter'):
            # redis-py
            for key in redis_client.scan_iter(match=pattern, count=100):
                # Extract installation_id from key
                # Format: github:app:installation:{installation_id}:project
                parts = key.split(":")
                if len(parts) == 5:
                    installation_id = int(parts[3])
                    project_id = redis_client.get(key)
                    if project_id:
                        mappings[installation_id] = project_id
        else:
            # Upstash REST
            for key in redis_client.scan_iter(pattern, count=100):
                parts = key.split(":")
                if len(parts) == 5:
                    installation_id = int(parts[3])
                    project_id = redis_client.get(key)
                    if project_id:
                        mappings[installation_id] = project_id

        return mappings
    except Exception as e:
        logger.error(f"Error getting installation mappings: {e}")
        return {}
