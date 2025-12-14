import { NextRequest, NextResponse } from 'next/server';
import { requireProjectId } from '@/lib/project';

const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000';

function backendError(status: number) {
  return status >= 500 ? 502 : status;
}

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const projectId = await requireProjectId(request);
    const limitParam = searchParams.get('limit') || '20';
    const limit = Math.min(Math.max(parseInt(limitParam, 10) || 20, 1), 50);

    const params = new URLSearchParams();
    params.set('project_id', projectId);
    params.set('limit', String(limit));

    const response = await fetch(`${backendUrl}/cluster-jobs?${params.toString()}`, {
      signal: AbortSignal.timeout(15000),
    });
    if (!response.ok) {
      console.error(`Backend returned ${response.status} for cluster jobs GET`);
      return NextResponse.json({ error: 'Failed to fetch cluster jobs' }, { status: backendError(response.status) });
    }
    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error: any) {
    if (error?.message === 'project_id is required') {
      return NextResponse.json({ error: 'project_id is required' }, { status: 400 });
    }
    if (error?.name === 'AbortError' || error?.message?.includes('timeout')) {
      return NextResponse.json({ error: 'Backend request timed out' }, { status: 503 });
    }
    console.error('Error fetching cluster jobs:', error);
    return NextResponse.json({ error: 'Failed to fetch cluster jobs' }, { status: 500 });
  }
}

export async function POST(request: NextRequest) {
  try {
    const projectId = await requireProjectId(request);
    let payload: string | undefined;
    try {
      const text = await request.text();
      payload = text ? text : undefined;
    } catch {
      payload = undefined;
    }

    const response = await fetch(`${backendUrl}/cluster-jobs?project_id=${projectId}`, {
      method: 'POST',
      headers: payload ? { 'Content-Type': 'application/json' } : undefined,
      body: payload,
      signal: AbortSignal.timeout(30000),
    });
    if (!response.ok) {
      console.error(`Backend returned ${response.status} for cluster job POST`);
      const errorBody = await response.json().catch(() => ({}));
      const message = errorBody?.error || 'Failed to start clustering job';
      return NextResponse.json({ error: message }, { status: backendError(response.status) });
    }
    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error: any) {
    if (error?.message === 'project_id is required') {
      return NextResponse.json({ error: 'project_id is required' }, { status: 400 });
    }
    if (error?.name === 'AbortError' || error?.message?.includes('timeout')) {
      return NextResponse.json({ error: 'Backend request timed out' }, { status: 503 });
    }
    console.error('Error starting cluster job:', error);
    return NextResponse.json({ error: 'Failed to start clustering job' }, { status: 500 });
  }
}
