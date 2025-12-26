import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';
import { getProjectId } from '@/lib/project';
import { getRedis } from '@/lib/redis';

const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000';

/**
 * GitHub App installation callback handler.
 *
 * This route is called by GitHub after a user installs the GitHub App.
 * It stores the installation details in Prisma and Redis, then triggers
 * an initial sync of all open issues from the installation's repositories.
 *
 * Flow:
 * 1. Extract installation_id from query params
 * 2. Get current project_id from session
 * 3. Fetch installation details from GitHub using GitHub App JWT
 * 4. Store installation in Prisma
 * 5. Store repositories in Prisma
 * 6. Store installation->project mapping in Redis (for backend webhook lookups)
 * 7. Store repo enablement status in Redis
 * 8. Trigger initial sync via backend
 * 9. Redirect to settings page
 */
export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const installationId = searchParams.get('installation_id');
  const setupAction = searchParams.get('setup_action');

  if (!installationId) {
    return NextResponse.redirect(
      new URL('/settings/integrations?error=no_installation_id', request.url)
    );
  }

  // Get current project from session
  const projectId = await getProjectId(request);
  if (!projectId) {
    return NextResponse.redirect(
      new URL('/settings/integrations?error=not_authenticated', request.url)
    );
  }

  try {
    // Fetch installation details from GitHub using GitHub App JWT
    const installationData = await fetchInstallationDetails(Number(installationId));

    // Store installation in Prisma
    const installation = await prisma.gitHubAppInstallation.upsert({
      where: { installationId: Number(installationId) },
      create: {
        projectId,
        installationId: Number(installationId),
        accountLogin: installationData.account.login,
        accountType: installationData.account.type,
        targetType: installationData.target_type,
        permissions: installationData.permissions || {},
      },
      update: {
        accountLogin: installationData.account.login,
        permissions: installationData.permissions || {},
        suspendedAt: null,
        updatedAt: new Date(),
      },
    });

    // Fetch repositories for this installation
    const reposData = await fetchInstallationRepos(Number(installationId));

    // Store repositories in Prisma
    for (const repo of reposData) {
      await prisma.gitHubAppRepository.upsert({
        where: { repositoryId: repo.id },
        create: {
          installationId: installation.id,
          repositoryId: repo.id,
          fullName: repo.full_name,
          private: repo.private || false,
          enabled: true, // Default to enabled
        },
        update: {
          fullName: repo.full_name,
          private: repo.private || false,
        },
      });
    }

    // Store mapping in Redis for backend webhook lookups
    const redis = getRedis();
    if (redis) {
      // Store installation -> project mapping
      const installationKey = `github:app:installation:${installationId}:project`;
      await redis.set(installationKey, projectId);

      // Store repo enablement status
      for (const repo of reposData) {
        const repoKey = `github:app:repo:${repo.id}:enabled`;
        await redis.set(repoKey, '1'); // Enabled by default
      }
    }

    // Trigger initial sync via backend (background task)
    // This backfills all existing open issues from the installation
    try {
      fetch(
        `${backendUrl}/ingest/github/app/sync/${installationId}?project_id=${projectId}`,
        {
          method: 'POST',
          signal: AbortSignal.timeout(5000), // Short timeout for background task
        }
      ).catch((error) => {
        console.error('Initial sync trigger failed (non-blocking):', error);
        // Non-blocking - sync can be triggered manually later
      });
    } catch (error) {
      console.error('Failed to trigger initial sync:', error);
      // Non-blocking - user can trigger sync manually
    }

    return NextResponse.redirect(
      new URL('/settings/integrations?github_app_installed=true', request.url)
    );
  } catch (error) {
    console.error('Error handling GitHub App callback:', error);
    const errorMessage = error instanceof Error ? error.message : 'installation_failed';
    return NextResponse.redirect(
      new URL(`/settings/integrations?error=${errorMessage}`, request.url)
    );
  }
}

/**
 * Fetch installation details from GitHub using GitHub App JWT.
 */
async function fetchInstallationDetails(installationId: number): Promise<any> {
  const jwt = generateGitHubAppJWT();

  const response = await fetch(
    `https://api.github.com/app/installations/${installationId}`,
    {
      headers: {
        Authorization: `Bearer ${jwt}`,
        Accept: 'application/vnd.github+json',
        'User-Agent': 'Soulcaster/1.0',
      },
      signal: AbortSignal.timeout(10000),
    }
  );

  if (!response.ok) {
    throw new Error(`Failed to fetch installation: ${response.status} ${response.statusText}`);
  }

  return response.json();
}

/**
 * Fetch repositories for an installation.
 */
async function fetchInstallationRepos(installationId: number): Promise<any[]> {
  // First get an installation token
  const jwt = generateGitHubAppJWT();

  const tokenResponse = await fetch(
    `https://api.github.com/app/installations/${installationId}/access_tokens`,
    {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${jwt}`,
        Accept: 'application/vnd.github+json',
        'User-Agent': 'Soulcaster/1.0',
      },
      signal: AbortSignal.timeout(10000),
    }
  );

  if (!tokenResponse.ok) {
    throw new Error(`Failed to get installation token: ${tokenResponse.status}`);
  }

  const tokenData = await tokenResponse.json();
  const installationToken = tokenData.token;

  // Now fetch repositories using the installation token
  const reposResponse = await fetch('https://api.github.com/installation/repositories', {
    headers: {
      Authorization: `Bearer ${installationToken}`,
      Accept: 'application/vnd.github+json',
      'User-Agent': 'Soulcaster/1.0',
    },
    signal: AbortSignal.timeout(10000),
  });

  if (!reposResponse.ok) {
    throw new Error(`Failed to fetch repositories: ${reposResponse.status}`);
  }

  const reposData = await reposResponse.json();
  return reposData.repositories || [];
}

/**
 * Generate GitHub App JWT for authentication.
 *
 * GitHub Apps authenticate using a JWT signed with their private key.
 */
function generateGitHubAppJWT(): string {
  const appId = process.env.GITHUB_APP_ID;
  const privateKey = process.env.GITHUB_APP_PRIVATE_KEY;

  if (!appId) {
    throw new Error('GITHUB_APP_ID environment variable is required');
  }
  if (!privateKey) {
    throw new Error('GITHUB_APP_PRIVATE_KEY environment variable is required');
  }

  // Import jsonwebtoken dynamically (Next.js edge runtime compatibility)
  const jwt = require('jsonwebtoken');

  // Handle escaped newlines in private key
  const formattedKey = privateKey.replace(/\\n/g, '\n');

  const now = Math.floor(Date.now() / 1000);
  const payload = {
    iat: now, // Issued at time
    exp: now + 600, // Expires in 10 minutes
    iss: appId, // Issuer (GitHub App ID)
  };

  return jwt.sign(payload, formattedKey, { algorithm: 'RS256' });
}
