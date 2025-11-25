import { NextResponse } from 'next/server';
import { Redis } from '@upstash/redis';
import { Index } from '@upstash/vector';

const redis = new Redis({
  url: process.env.UPSTASH_REDIS_REST_URL!,
  token: process.env.UPSTASH_REDIS_REST_TOKEN!,
});

const vectorIndex = new Index({
  url: process.env.UPSTASH_VECTOR_REST_URL!,
  token: process.env.UPSTASH_VECTOR_REST_TOKEN!,
});

/**
 * Reset all clustering data and mark all feedback as unclustered
 * POST /api/clusters/reset
 */
export async function POST() {
  try {
    console.log('[Reset] Starting cluster reset...');

    // Get all cluster IDs
    const clusterIds = (await redis.smembers('clusters:all')) as string[];
    console.log(`[Reset] Found ${clusterIds.length} clusters to delete`);

    // Delete all cluster data
    for (const clusterId of clusterIds) {
      await redis.del(`cluster:${clusterId}`);
      await redis.del(`cluster:items:${clusterId}`);
    }

    // Clear clusters:all set
    await redis.del('clusters:all');

    // Clear Upstash Vector index
    console.log('[Reset] Clearing vector index...');
    try {
      await vectorIndex.reset();
      console.log('[Reset] Vector index cleared');
    } catch (vectorError) {
      console.error('[Reset] Error clearing vector index:', vectorError);
      // Continue anyway - vector index may be empty
    }

    // Get all feedback IDs from the created sorted set
    const feedbackIds = (await redis.zrange('feedback:created', 0, -1)) as string[];
    console.log(`[Reset] Found ${feedbackIds.length} feedback items to reset`);

    // Mark all feedback as unclustered and clear stored embeddings
    for (const feedbackId of feedbackIds) {
      await redis.hset(`feedback:${feedbackId}`, { clustered: 'false' });
      await redis.hdel(`feedback:${feedbackId}`, 'embedding');
      await redis.sadd('feedback:unclustered', feedbackId);
    }

    console.log('[Reset] Reset complete');

    return NextResponse.json({
      success: true,
      message: 'Clustering data reset successfully',
      deletedClusters: clusterIds.length,
      resetFeedback: feedbackIds.length,
    });
  } catch (error) {
    console.error('[Reset] Error resetting clusters:', error);
    return NextResponse.json(
      {
        success: false,
        error: 'Failed to reset clustering data',
        details: error instanceof Error ? error.message : 'Unknown error',
      },
      { status: 500 }
    );
  }
}
