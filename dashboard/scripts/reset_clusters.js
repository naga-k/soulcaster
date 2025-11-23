#!/usr/bin/env node
const path = require('path');
const { Redis } = require('@upstash/redis');
const fetch = globalThis.fetch;

require('dotenv').config({ path: path.resolve(__dirname, '../.env') });

const redisUrl = process.env.UPSTASH_REDIS_REST_URL;
const redisToken = process.env.UPSTASH_REDIS_REST_TOKEN;
const runEndpoint = process.env.CLUSTER_RUN_ENDPOINT || 'http://localhost:3000/api/clusters/run';
const chunkSize = Number(process.env.CLUSTER_CHUNK_SIZE || '10');
const delayMs = Number(process.env.CLUSTER_DELAY_MS || '500');

if (!redisUrl || !redisToken) {
  console.error('Missing Redis configuration (UPSTASH_REDIS_REST_URL / TOKEN).');
  process.exit(1);
}

if (!fetch) {
  console.error('Node does not provide fetch; use Node 18+ or add a fetch polyfill.');
  process.exit(1);
}

const redis = new Redis({ url: redisUrl, token: redisToken });

function chunkArray(array, size) {
  const chunks = [];
  for (let i = 0; i < array.length; i += size) {
    chunks.push(array.slice(i, i + size));
  }
  return chunks;
}

async function resetClusteredFlag(feedbackIds) {
  for (const id of feedbackIds) {
    await redis.hset(`feedback:${id}`, { clustered: 'false' });
  }
}

async function markChunkAsUnclustered(chunk) {
  await redis.del('feedback:unclustered');
  for (const id of chunk) {
    await redis.hset(`feedback:${id}`, { clustered: 'false' });
    await redis.sadd('feedback:unclustered', id);
  }
}

async function runThrottledClustering(chunk, index, totalChunks) {
  console.log(`Processing chunk ${index + 1}/${totalChunks} with ${chunk.length} items`);
  const response = await fetch(runEndpoint, { method: 'POST' });
  if (!response.ok) {
    throw new Error(`Clustering API failed with ${response.status}`);
  }
  console.log('Chunk processed, waiting for next run...');
  if (index + 1 < totalChunks) {
    await new Promise((resolve) => setTimeout(resolve, delayMs));
  }
}

(async () => {
  const feedbackIds = await redis.zrange('feedback:created', 0, -1);
  if (feedbackIds.length === 0) {
    console.log('No feedback items found. Nothing to reset.');
    return;
  }

  console.log(`Resetting ${feedbackIds.length} feedback items to clustered=false`);
  await resetClusteredFlag(feedbackIds);

  const chunks = chunkArray(feedbackIds, chunkSize);
  for (let index = 0; index < chunks.length; index += 1) {
    const chunk = chunks[index];
    await markChunkAsUnclustered(chunk);
    await runThrottledClustering(chunk, index, chunks.length);
  }

  console.log('Finished resetting feedback and re-running clustering in chunks.');
})().catch((error) => {
  console.error('Script failed:', error);
  process.exit(1);
});
