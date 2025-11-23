import { NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

export async function GET() {
  const response = await fetch(`${BACKEND_URL}/config/reddit/subreddits`, {
    cache: 'no-store',
  });

  const data = await response.json();
  return NextResponse.json(data, { status: response.status });
}

export async function POST(request: Request) {
  const payload = await request.json();
  const response = await fetch(`${BACKEND_URL}/config/reddit/subreddits`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  const data = await response.json();
  return NextResponse.json(data, { status: response.status });
}
