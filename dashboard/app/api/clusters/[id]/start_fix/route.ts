import { NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

/**
 * Initiates a fix operation for the cluster specified by the route `id` by proxying a POST to the backend.
 *
 * @param params - Promise resolving to route parameters; must include `id`, the cluster identifier.
 * @returns The backend's JSON response when the fix is started; on failure returns an error object `{ error: 'Failed to start fix' }` with HTTP status 500.
 */
export async function POST(request: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await params;

    // Validate ID format (UUID or numeric)
    if (!id || !/^[a-zA-Z0-9-]+$/.test(id)) {
      return NextResponse.json({ error: 'Invalid cluster ID' }, { status: 400 });
    }

    // Fetch cluster details to get context
    const clusterResponse = await fetch(`${BACKEND_URL}/clusters/${encodeURIComponent(id)}`);
    if (!clusterResponse.ok) {
      return NextResponse.json({ error: 'Failed to load cluster' }, { status: 502 });
    }
    const clusterData = await clusterResponse.json();

    // Determine repo based on cluster data
    let repoOwner = process.env.GITHUB_OWNER;
    let repoName = process.env.GITHUB_REPO;

    const repoFromCluster = clusterData?.github_repo_url
      ? clusterData.github_repo_url.match(/github\.com\/([^/]+)\/([^/]+)/)
      : null;
    if (repoFromCluster) {
      repoOwner = repoFromCluster[1];
      repoName = repoFromCluster[2].replace(/\.git$/, '');
    }

    if (clusterData && clusterData.feedback_items) {
      const hasManualFeedback = clusterData.feedback_items.some(
        (item: any) => item.source === 'manual'
      );
      if (hasManualFeedback && (!repoOwner || !repoName)) {
        repoOwner = 'naga-k';
        repoName = 'bad-ux-mart';
      }
    }

    // Trigger the agent
    try {
      const triggerUrl = new URL('/api/trigger-agent', new URL(request.url).origin).toString();
      console.log(`Triggering agent at ${triggerUrl} for ${repoOwner}/${repoName}`);

      const triggerResponse = await fetch(triggerUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          issue_url: clusterData?.github_pr_url || undefined,
          context:
            clusterData?.issue_description || clusterData?.summary || `Fix for cluster ${id}`,
          issue_description: clusterData?.issue_description || clusterData?.summary,
          issue_title: clusterData?.issue_title || clusterData?.title,
          owner: repoOwner,
          repo: repoName,
          repo_url: clusterData?.github_repo_url,
          cluster_id: id,
        }),
      });

      if (!triggerResponse.ok) {
        const errorText = await triggerResponse.text();
        throw new Error(`Trigger agent responded with ${triggerResponse.status}: ${errorText}`);
      }

      const triggerData = await triggerResponse.json();
      console.log('Agent triggered successfully:', triggerData);
    } catch (triggerError) {
      console.error('Error calling trigger-agent:', triggerError);
      return NextResponse.json({ error: 'Failed to trigger agent' }, { status: 502 });
    }

    const response = await fetch(`${BACKEND_URL}/clusters/${encodeURIComponent(id)}/start_fix`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`Backend responded with ${response.status}`);
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error starting fix:', error);
    return NextResponse.json({ error: 'Failed to start fix' }, { status: 500 });
  }
}
