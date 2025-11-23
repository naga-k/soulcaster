from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.main import app
from backend.models import AgentJob
from backend.store import (
    add_cluster,
    add_job,
    clear_clusters,
    clear_jobs,
    get_job,
    IssueCluster,
)


client = TestClient(app)


def setup_function():
    clear_clusters()
    clear_jobs()


def _seed_cluster():
    now = datetime.now(timezone.utc)
    cluster = IssueCluster(
        id=uuid4(),
        title="Test Cluster",
        summary="Test Summary",
        feedback_ids=[],
        status="new",
        created_at=now,
        updated_at=now,
    )
    add_cluster(cluster)
    return cluster


def test_create_job():
    cluster = _seed_cluster()
    response = client.post("/jobs", json={"cluster_id": str(cluster.id)})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "job_id" in data

    job = get_job(uuid4())  # We don't know ID, but we can search or rely on ID return
    # Better: verify ID returned is valid
    job_id = data["job_id"]
    job = get_job(job_id) # Should work if passing string, but get_job expects UUID usually?
    # store.py: get_job(job_id: UUID)
    # Let's convert string to UUID
    from uuid import UUID
    job = get_job(UUID(job_id))
    
    assert job is not None
    assert job.cluster_id == cluster.id
    assert job.status == "pending"


def test_update_job_status():
    cluster = _seed_cluster()
    now = datetime.now(timezone.utc)
    job = AgentJob(
        id=uuid4(),
        cluster_id=cluster.id,
        status="pending",
        created_at=now,
        updated_at=now,
    )
    add_job(job)

    response = client.patch(
        f"/jobs/{job.id}", json={"status": "running"}
    )

    assert response.status_code == 200
    
    updated = get_job(job.id)
    assert updated.status == "running"


def test_update_job_logs():
    cluster = _seed_cluster()
    now = datetime.now(timezone.utc)
    job = AgentJob(
        id=uuid4(),
        cluster_id=cluster.id,
        status="pending",
        created_at=now,
        updated_at=now,
    )
    add_job(job)

    log_content = "Starting fix process..."
    response = client.patch(
        f"/jobs/{job.id}", json={"logs": log_content}
    )

    assert response.status_code == 200
    
    updated = get_job(job.id)
    assert updated.logs == log_content


def test_get_job_details():
    cluster = _seed_cluster()
    now = datetime.now(timezone.utc)
    job = AgentJob(
        id=uuid4(),
        cluster_id=cluster.id,
        status="pending",
        logs="Initial logs",
        created_at=now,
        updated_at=now,
    )
    add_job(job)

    response = client.get(f"/jobs/{job.id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(job.id)
    assert data["status"] == "pending"
    assert data["logs"] == "Initial logs"


def test_get_cluster_jobs():
    cluster = _seed_cluster()
    now = datetime.now(timezone.utc)
    
    # Create 2 jobs
    job1 = AgentJob(
        id=uuid4(),
        cluster_id=cluster.id,
        status="pending",
        created_at=now,
        updated_at=now,
    )
    add_job(job1)
    
    job2 = AgentJob(
        id=uuid4(),
        cluster_id=cluster.id,
        status="success",
        created_at=now,
        updated_at=now,
    )
    add_job(job2)

    response = client.get(f"/clusters/{cluster.id}/jobs")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    ids = {item["id"] for item in data}
    assert str(job1.id) in ids
    assert str(job2.id) in ids
