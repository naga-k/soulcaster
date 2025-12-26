# Implementation Plan: Vercel Blob Log Storage with Real-Time Viewing

## Overview

Migrate job logs from Redis to Vercel Blob storage using a hybrid approach:
- **Redis (transient)**: Store logs during active job execution for real-time viewing
- **Vercel Blob (permanent)**: Archive logs on job completion for long-term storage
- **Auto-switching frontend**: Fetch from Redis for running jobs, Blob for completed jobs

## Benefits

- **Reduce Redis memory**: ~99% reduction (35MB → 250KB for active jobs only)
- **Cost-effective**: Vercel Blob storage ~$0.03/month vs Redis memory pricing
- **Real-time viewing**: No impact on current 2s polling experience
- **Long-term retention**: Logs persist in Blob beyond 7-day Redis TTL

## Architecture

```
Job Running → Redis (transient, TTL) → Frontend polls every 2s
Job Completes → Archive to Blob → Delete from Redis → Frontend fetches from Blob
```

## Implementation Steps

### Phase 1: Backend Infrastructure

#### 1. Create Blob Storage Client (`backend/blob_storage.py`) - NEW FILE

```python
from vercel_blob import put, get, delete
import os
from uuid import UUID

BLOB_TOKEN = os.getenv("BLOB_READ_WRITE_TOKEN")

def upload_job_logs_to_blob(job_id: UUID, logs: str) -> str:
    """Upload logs to Vercel Blob. Returns blob_url."""
    response = put(
        f"logs/{job_id}.txt",
        logs,
        {
            "access": "public",
            "token": BLOB_TOKEN
        }
    )
    return response["url"]

def fetch_job_logs_from_blob(blob_url: str) -> str:
    """Fetch logs from Vercel Blob."""
    import requests
    response = requests.get(blob_url)
    response.raise_for_status()
    return response.text

def delete_job_logs_from_blob(blob_url: str) -> bool:
    """Delete logs from Vercel Blob."""
    try:
        delete(blob_url, {"token": BLOB_TOKEN})
        return True
    except Exception:
        return False
```

#### 2. Update AgentJob Model (`backend/models.py`)

Add field after line 28:
```python
blob_url: Optional[str] = None  # URL to archived logs in Vercel Blob
```

#### 3. Update Store Layer (`backend/store.py`)

**Add method to RedisStore class (after line 2097):**

```python
def archive_job_logs_to_blob(self, job_id: UUID) -> Optional[str]:
    """
    Archive job logs from Redis to Vercel Blob.

    1. Fetch all logs from Redis list
    2. Upload to Blob
    3. Update job with blob_url
    4. Delete Redis logs (don't wait for TTL)

    Returns: blob_url if successful, None otherwise
    """
    from blob_storage import upload_job_logs_to_blob

    # Fetch all log chunks from Redis
    chunks, _, _ = self.get_job_logs(job_id, cursor=0, limit=100000)
    if not chunks:
        logger.warning(f"No logs found for job {job_id}")
        return None

    # Concatenate all chunks
    full_logs = "\n".join(chunks)

    # Upload to Blob
    try:
        blob_url = upload_job_logs_to_blob(job_id, full_logs)
        logger.info(f"Uploaded logs for job {job_id} to Blob: {blob_url}")
    except Exception as e:
        logger.error(f"Failed to upload logs to Blob for job {job_id}: {e}")
        return None

    # Update job record with blob_url
    try:
        self.update_job(job_id, blob_url=blob_url)
    except Exception as e:
        logger.error(f"Failed to update job {job_id} with blob_url: {e}")
        return None

    # Delete Redis logs to free memory
    try:
        logs_key = self._job_logs_key(job_id)
        self.client.delete(logs_key)
        logger.info(f"Deleted Redis logs for job {job_id}")
    except Exception as e:
        logger.warning(f"Failed to delete Redis logs for job {job_id}: {e}")

    return blob_url
```

**Add global function (after line 2810):**

```python
def archive_job_logs_to_blob(job_id: UUID) -> Optional[str]:
    """Archive job logs to Vercel Blob storage."""
    if hasattr(_STORE, "archive_job_logs_to_blob"):
        return _STORE.archive_job_logs_to_blob(job_id)
    return None
```

#### 4. Hook Archive into Job Completion (`backend/agent_runner/sandbox.py`)

**Add import (line 16):**
```python
from store import append_job_log, get_job, update_job, update_cluster, archive_job_logs_to_blob
```

**After job success (add after line 801):**
```python
# Archive logs to Blob
try:
    await asyncio.to_thread(archive_job_logs_to_blob, job_id)
    logger.info(f"Job {job_id} logs archived to Blob")
except Exception as e:
    logger.warning(f"Failed to archive logs for job {job_id}: {e}")
```

**After job failure (add after line 859):**
```python
# Archive logs to Blob
try:
    await asyncio.to_thread(archive_job_logs_to_blob, job_id)
    logger.info(f"Job {job_id} logs archived to Blob")
except Exception as e:
    logger.warning(f"Failed to archive logs for job {job_id}: {e}")
```

#### 5. Add Backend API Endpoint (`backend/main.py`)

**Add after line 2297:**

```python
@app.get("/jobs/{job_id}/logs/blob")
def get_job_logs_from_blob(
    job_id: UUID,
    project_id: Optional[str] = Query(None),
):
    """
    Retrieve archived logs from Vercel Blob for completed jobs.

    Returns:
        200: {"blob_url": "https://...", "logs": "..."}
        404: Job not found
        410: Logs not yet archived (still in Redis)
    """
    pid = _require_project_id(project_id)
    job = get_job(job_id)

    if not job or str(job.project_id) != pid:
        raise HTTPException(status_code=404, detail="Job not found")

    if not job.blob_url:
        raise HTTPException(status_code=410, detail="Logs not yet archived to Blob")

    try:
        from blob_storage import fetch_job_logs_from_blob
        logs = fetch_job_logs_from_blob(job.blob_url)
        return {
            "job_id": str(job_id),
            "blob_url": job.blob_url,
            "logs": logs,
        }
    except Exception as e:
        logger.error(f"Failed to fetch logs from Blob: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch logs from Blob")
```

**Add import at top:**
```python
from store import (
    # ... existing imports ...
    archive_job_logs_to_blob,
)
```

### Phase 2: Dashboard Frontend

#### 1. Update API Route (`dashboard/app/api/jobs/[id]/job-logs/route.ts`)

Replace the GET function with intelligent routing:

```typescript
export async function GET(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await params;
    const projectId = await requireProjectId(request);
    const { searchParams } = new URL(request.url);

    // Fetch job metadata to determine storage location
    const jobResponse = await fetch(
      `${backendUrl}/jobs/${encodeURIComponent(id)}?project_id=${projectId}`,
      { signal: AbortSignal.timeout(10000) }
    );

    if (!jobResponse.ok) {
      return NextResponse.json({ error: 'Job not found' }, { status: 404 });
    }

    const job = await jobResponse.json();

    // For completed jobs with blob_url, fetch from Blob
    if ((job.status === 'success' || job.status === 'failed') && job.blob_url) {
      const blobResponse = await fetch(
        `${backendUrl}/jobs/${encodeURIComponent(id)}/logs/blob?project_id=${projectId}`,
        { signal: AbortSignal.timeout(15000) }
      );

      if (blobResponse.ok) {
        const blobData = await blobResponse.json();
        return NextResponse.json({
          source: 'blob',
          chunks: [blobData.logs],
          next_cursor: 0,
          has_more: false,
        });
      }
      // Fallback to Redis if Blob fetch fails
    }

    // Fetch from Redis (running jobs or fallback)
    const cursor = searchParams.get('cursor') || '0';
    const limit = searchParams.get('limit') || '200';
    const backendParams = new URLSearchParams();
    backendParams.set('project_id', projectId);
    backendParams.set('cursor', cursor);
    backendParams.set('limit', limit);

    const redisResponse = await fetch(
      `${backendUrl}/jobs/${encodeURIComponent(id)}/logs?${backendParams.toString()}`,
      { signal: AbortSignal.timeout(15000) }
    );

    if (!redisResponse.ok) {
      return NextResponse.json({ error: 'Failed to fetch logs' }, { status: 502 });
    }

    const data = await redisResponse.json();
    return NextResponse.json({ ...data, source: 'redis' });
  } catch (error: any) {
    console.error('Error fetching job logs:', error);
    return NextResponse.json(
      { error: error.message || 'Internal server error' },
      { status: 500 }
    );
  }
}
```

#### 2. Update Cluster Page (`dashboard/app/(dashboard)/dashboard/clusters/[id]/page.tsx`)

Modify `fetchJobLogs` function (lines 97-125) to handle Blob source:

```typescript
const fetchJobLogs = useCallback(
  async (jobId: string, opts?: { append?: boolean }) => {
    const append = opts?.append ?? false;

    // For completed jobs on first load, try Blob (no pagination needed)
    const job = fixJobs.find(j => j.id === jobId);
    const isCompleted = job && (job.status === 'success' || job.status === 'failed');

    if (isCompleted && !append) {
      const response = await fetch(`/api/jobs/${encodeURIComponent(jobId)}/job-logs`);
      if (!response.ok) throw new Error('Failed to fetch logs');

      const payload = await response.json();
      if (payload.source === 'blob') {
        // Full logs from Blob - no pagination needed
        setLogText(payload.chunks.join(''));
        setIsTailingLogs(false); // Stop tailing for completed jobs
        return;
      }
    }

    // Redis path (running jobs or fallback)
    const cursor = append ? logCursor : 0;
    const response = await fetch(
      `/api/jobs/${encodeURIComponent(jobId)}/job-logs?cursor=${cursor}&limit=200`
    );
    if (!response.ok) throw new Error('Failed to fetch logs');

    const payload = await response.json();
    const chunks = (payload?.chunks as string[]) || [];
    const nextCursor = typeof payload?.next_cursor === 'number'
      ? payload.next_cursor
      : cursor + chunks.length;

    if (append) {
      setLogText((prev) => prev + chunks.join(''));
    } else {
      setLogText(chunks.join(''));
    }
    setLogCursor(nextCursor);
    setIsTailingLogs(
      Boolean(payload?.has_more) || fixJobs.some((j) => j.id === jobId && j.status === 'running')
    );
  },
  [logCursor, fixJobs]
);
```

### Phase 3: Environment & Dependencies

#### 1. Backend Requirements (`backend/requirements.txt`)

Add:
```
vercel-blob>=0.1.0
```

#### 2. Environment Variables

**Backend `.env`:**
```bash
BLOB_READ_WRITE_TOKEN=soulcaster_agent_logs_dev_READ_WRITE_TOKEN
```

**Update `.env.example`:**
```bash
# Vercel Blob Storage (for job logs archival)
BLOB_READ_WRITE_TOKEN=your_token_here
```

### Phase 4: Testing

#### Manual Testing Checklist

1. Start a new job → logs appear in real-time (Redis)
2. Job completes → logs archive to Blob automatically
3. View completed job → logs load from Blob
4. Verify Redis logs deleted after archival
5. Test fallback: disable Blob temporarily, verify Redis fallback works

#### Integration Points

- Backend: `pytest backend/tests -v`
- Dashboard: `npm test` (if tests exist)

### Phase 5: Deployment

1. **Backend deployment:**
   ```bash
   pip install -r backend/requirements.txt
   # Set BLOB_READ_WRITE_TOKEN in production
   # Restart backend service
   ```

2. **Dashboard deployment:**
   ```bash
   cd dashboard
   npm run build
   # Deploy to Vercel
   ```

3. **Verify:**
   - Check backend logs for "logs archived to Blob" messages
   - Monitor Vercel Blob dashboard
   - Test end-to-end flow with a test job

## Rollback Plan

If Blob integration fails:
1. Revert backend changes (remove archive calls)
2. Logs continue in Redis only (current behavior)
3. Frontend falls back to Redis API automatically
4. No data loss (logs remain in Redis with TTL)

## File Summary

### New Files
- `backend/blob_storage.py` - Blob client wrapper

### Modified Files
- `backend/models.py` - Add `blob_url` field
- `backend/store.py` - Add archive method
- `backend/agent_runner/sandbox.py` - Hook archival on completion
- `backend/main.py` - Add `/jobs/{id}/logs/blob` endpoint
- `backend/requirements.txt` - Add vercel-blob
- `dashboard/app/api/jobs/[id]/job-logs/route.ts` - Intelligent routing
- `dashboard/app/(dashboard)/dashboard/clusters/[id]/page.tsx` - Handle Blob source
- `.env.example` - Document BLOB_READ_WRITE_TOKEN

## Performance Impact

- **Redis memory**: ~99% reduction (35MB → 250KB)
- **Real-time logs**: No change (still 2s polling)
- **Completed logs**: 200-400ms latency (acceptable)
- **Cost**: ~$0.03/month for Blob storage

## Success Metrics

- Redis memory usage decreases by >90%
- All completed jobs have `blob_url` populated
- Zero log fetch errors in dashboard
- Real-time tailing experience unchanged
