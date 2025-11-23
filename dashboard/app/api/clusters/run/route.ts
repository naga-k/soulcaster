import { NextResponse } from 'next/server';
import { Redis } from '@upstash/redis';
import { getUnclusteredFeedbackIds, getFeedbackItem, getClusterIds } from '@/lib/redis';
import { clusterFeedbackBatch, generateClusterSummary, type ClusterData } from '@/lib/clustering';
import type { FeedbackItem } from '@/types';

const redis = new Redis({
  url: process.env.UPSTASH_REDIS_REST_URL!,
  token: process.env.UPSTASH_REDIS_REST_TOKEN!,
});

/**
 * Run clustering on unclustered feedback items
 * POST /api/clusters/run
 */
export async function POST() {
  try {
    console.log('[Clustering] Starting clustering job...');

    // Get unclustered feedback IDs
    const unclusteredIds = await getUnclusteredFeedbackIds();
    console.log(`[Clustering] Found ${unclusteredIds.length} unclustered items`);

    if (unclusteredIds.length === 0) {
      return NextResponse.json({
        success: true,
        message: 'No unclustered feedback to process',
        clustered: 0,
        newClusters: 0,
      });
    }

    // Fetch unclustered feedback items
    const feedbackItems = await Promise.all(unclusteredIds.map((id) => getFeedbackItem(id)));
    const validFeedback = feedbackItems.filter((item): item is FeedbackItem => item !== null);

    // Get existing clusters
    const existingClusterIds = await getClusterIds();
    const existingClusters: ClusterData[] = [];

    for (const clusterId of existingClusterIds) {
      const clusterData = await redis.hgetall(`cluster:${clusterId}`);
      if (!clusterData) continue;

      // Get feedback IDs in this cluster
      const feedbackIds = (await redis.smembers(`cluster:items:${clusterId}`)) as string[];

      // Parse centroid if it exists
      let centroid: number[] = [];
      if (clusterData.centroid && typeof clusterData.centroid === 'string') {
        try {
          centroid = JSON.parse(clusterData.centroid);
        } catch {
          centroid = [];
        }
      }

      existingClusters.push({
        id: clusterId,
        feedbackIds,
        centroid,
      });
    }

    console.log(`[Clustering] Processing against ${existingClusters.length} existing clusters`);

    // Run clustering with lower threshold for more aggressive grouping
    // 0.65 allows items with 65% similarity to cluster together
    const { results, updatedClusters } = await clusterFeedbackBatch(
      validFeedback,
      existingClusters,
      0.65 // similarity threshold (lower = more aggressive clustering)
    );

    // Track new clusters created
    const newClusterIds = new Set(results.filter((r) => r.isNewCluster).map((r) => r.clusterId));

    console.log(`[Clustering] Created ${newClusterIds.size} new clusters`);

    // Update Redis with clustering results
    for (const cluster of updatedClusters) {
      // Get feedback items for this cluster
      const clusterFeedback = await Promise.all(
        cluster.feedbackIds.map((id) => getFeedbackItem(id))
      );
      const validClusterFeedback = clusterFeedback.filter(
        (item): item is FeedbackItem => item !== null
      );

      // Generate summary
      const { title, summary, issueTitle, issueDescription, repoUrl } = await generateClusterSummary(
        validClusterFeedback
      );

      const timestamp = new Date().toISOString();

      // Check if cluster is new or existing
      const isNew = newClusterIds.has(cluster.id);

      if (isNew) {
        // Create new cluster
        const payload: Record<string, string> = {
          id: cluster.id,
          title,
          summary,
          status: 'new',
          created_at: timestamp,
          updated_at: timestamp,
          centroid: JSON.stringify(cluster.centroid),
        };
        if (issueTitle) payload.issue_title = issueTitle;
        if (issueDescription) payload.issue_description = issueDescription;
        if (repoUrl) payload.github_repo_url = repoUrl;

        await redis.hset(`cluster:${cluster.id}`, payload);
        // Add to clusters:all set to avoid using KEYS command
        await redis.sadd('clusters:all', cluster.id);
      } else {
        // Update existing cluster
        const updatePayload: Record<string, string> = {
          summary,
          updated_at: timestamp,
          centroid: JSON.stringify(cluster.centroid),
        };
        if (issueTitle) updatePayload.issue_title = issueTitle;
        if (issueDescription) updatePayload.issue_description = issueDescription;
        if (repoUrl) updatePayload.github_repo_url = repoUrl;

        await redis.hset(`cluster:${cluster.id}`, updatePayload);
      }

      // Update cluster items set
      await redis.del(`cluster:items:${cluster.id}`);
      if (cluster.feedbackIds.length > 0) {
        // Add items one by one to avoid TypeScript spread issues
        for (const feedbackId of cluster.feedbackIds) {
          await redis.sadd(`cluster:items:${cluster.id}`, feedbackId);
        }
      }

      // Mark feedback as clustered
      for (const feedbackId of cluster.feedbackIds) {
        await redis.hset(`feedback:${feedbackId}`, { clustered: 'true' });
      }
    }

    // Remove items from unclustered set
    if (unclusteredIds.length > 0) {
      // Remove items one by one to avoid TypeScript spread issues
      for (const id of unclusteredIds) {
        await redis.srem('feedback:unclustered', id);
      }
    }

    console.log('[Clustering] Clustering complete');

    return NextResponse.json({
      success: true,
      message: 'Clustering completed successfully',
      clustered: validFeedback.length,
      newClusters: newClusterIds.size,
      updatedClusters: updatedClusters.length - newClusterIds.size,
    });
  } catch (error) {
    console.error('[Clustering] Error running clustering:', error);
    return NextResponse.json(
      {
        success: false,
        error: 'Failed to run clustering',
        details: error instanceof Error ? error.message : 'Unknown error',
      },
      { status: 500 }
    );
  }
}
