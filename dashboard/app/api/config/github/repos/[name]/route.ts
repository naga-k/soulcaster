import { NextResponse } from 'next/server';
import { Redis } from '@upstash/redis';

const redis = new Redis({
  url: process.env.UPSTASH_REDIS_REST_URL!,
  token: process.env.UPSTASH_REDIS_REST_TOKEN!,
});

/**
 * DELETE /api/config/github/repos/[name]
 * Remove a GitHub repository from configuration
 * Name should be URL-encoded "owner/repo" (e.g., "anthropics%2Fclaude-code")
 */
export async function DELETE(
  request: Request,
  { params }: { params: Promise<{ name: string }> }
) {
  try {
    const { name } = await params;

    // Decode URL-encoded repo name (e.g., "anthropics%2Fclaude-code" -> "anthropics/claude-code")
    const repoName = decodeURIComponent(name);

    console.log(`[GitHub] Removing repo: ${repoName}`);

    // Check if repo exists
    const repoData = await redis.hgetall(`github:repo:${repoName}`);
    if (!repoData || Object.keys(repoData).length === 0) {
      return NextResponse.json(
        { error: 'Repository not found' },
        { status: 404 }
      );
    }

    // Remove repo configuration
    await redis.del(`github:repo:${repoName}`);

    // Remove from repos set
    await redis.srem('github:repos', repoName);

    // Optionally: Remove associated feedback items (or keep them for history)
    // For now, we'll keep the feedback items but they won't be updated
    // Future enhancement: Add flag to delete associated feedback

    console.log(`[GitHub] Removed repo: ${repoName}`);

    return NextResponse.json({
      message: `Repository ${repoName} removed successfully`,
    });
  } catch (error) {
    console.error('[GitHub] Error removing repo:', error);
    return NextResponse.json(
      {
        error: 'Failed to remove repository',
        detail: error instanceof Error ? error.message : 'Unknown error',
      },
      { status: 500 }
    );
  }
}
