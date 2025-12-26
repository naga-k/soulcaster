-- CreateTable
CREATE TABLE "GitHubAppInstallation" (
    "id" TEXT NOT NULL,
    "projectId" TEXT NOT NULL,
    "installationId" INTEGER NOT NULL,
    "accountLogin" TEXT NOT NULL,
    "accountType" TEXT NOT NULL,
    "targetType" TEXT NOT NULL,
    "permissions" JSONB NOT NULL,
    "installedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    "suspendedAt" TIMESTAMP(3),

    CONSTRAINT "GitHubAppInstallation_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "GitHubAppRepository" (
    "id" TEXT NOT NULL,
    "installationId" TEXT NOT NULL,
    "repositoryId" INTEGER NOT NULL,
    "fullName" TEXT NOT NULL,
    "private" BOOLEAN NOT NULL DEFAULT false,
    "enabled" BOOLEAN NOT NULL DEFAULT true,
    "addedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "GitHubAppRepository_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "GitHubAppInstallation_installationId_key" ON "GitHubAppInstallation"("installationId");

-- CreateIndex
CREATE INDEX "GitHubAppInstallation_projectId_idx" ON "GitHubAppInstallation"("projectId");

-- CreateIndex
CREATE INDEX "GitHubAppInstallation_installationId_idx" ON "GitHubAppInstallation"("installationId");

-- CreateIndex
CREATE UNIQUE INDEX "GitHubAppRepository_repositoryId_key" ON "GitHubAppRepository"("repositoryId");

-- CreateIndex
CREATE INDEX "GitHubAppRepository_installationId_idx" ON "GitHubAppRepository"("installationId");

-- CreateIndex
CREATE INDEX "GitHubAppRepository_repositoryId_idx" ON "GitHubAppRepository"("repositoryId");

-- CreateIndex
CREATE INDEX "GitHubAppRepository_fullName_idx" ON "GitHubAppRepository"("fullName");

-- AddForeignKey
ALTER TABLE "GitHubAppInstallation" ADD CONSTRAINT "GitHubAppInstallation_projectId_fkey" FOREIGN KEY ("projectId") REFERENCES "Project"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "GitHubAppRepository" ADD CONSTRAINT "GitHubAppRepository_installationId_fkey" FOREIGN KEY ("installationId") REFERENCES "GitHubAppInstallation"("id") ON DELETE CASCADE ON UPDATE CASCADE;
