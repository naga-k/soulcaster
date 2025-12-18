'use client';

import { useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import IntegrationCard, { IntegrationConfig } from '@/components/settings/IntegrationCard';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

export default function IntegrationsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const tabParam = searchParams.get('tab') as 'monitoring' | 'analytics' | null;
  const [activeTab, setActiveTab] = useState<'monitoring' | 'analytics'>(tabParam || 'monitoring');

  // State for integration configs (will be loaded from backend)
  const [integrationConfigs, setIntegrationConfigs] = useState<{
    splunk: IntegrationConfig;
    datadog: IntegrationConfig;
    posthog: IntegrationConfig;
    sentry: IntegrationConfig;
  }>({
    splunk: {
      name: 'Splunk',
      icon: '🔍',
      description: 'Monitor logs and trigger alerts via webhook',
      enabled: false,
      fields: [
        {
          id: 'webhook_token',
          label: 'Webhook Token',
          type: 'password',
          placeholder: 'Enter your webhook token',
          helpText: 'This token will be used to authenticate webhook requests',
          required: true,
        },
        {
          id: 'webhook_url',
          label: 'Webhook URL',
          type: 'text',
          placeholder: `${BACKEND_URL}/webhook/splunk`,
          helpText: 'Use this URL in your Splunk webhook configuration',
          copyButton: true,
          readOnly: true,
        },
        {
          id: 'allowed_searches',
          label: 'Allowed Searches',
          type: 'textarea',
          placeholder: 'Enter allowed search names (one per line)',
          helpText: 'Only alerts from these saved searches will be processed',
        },
      ],
    },
    datadog: {
      name: 'Datadog',
      icon: '🐕',
      description: 'Receive monitor alerts and metrics',
      enabled: false,
      fields: [
        {
          id: 'webhook_secret',
          label: 'Webhook Secret (Optional)',
          type: 'password',
          placeholder: 'Enter webhook secret for validation',
          helpText: 'Leave empty to accept all webhook requests',
        },
        {
          id: 'allowed_monitors',
          label: 'Allowed Monitor IDs',
          type: 'multiselect',
          placeholder: 'Comma-separated monitor IDs, or "*" for all',
          defaultValue: '*',
          helpText: 'Use "*" to allow all monitors, or specify IDs like "123456,789012"',
        },
      ],
    },
    posthog: {
      name: 'PostHog',
      icon: '📊',
      description: 'Track product analytics events',
      enabled: false,
      fields: [
        {
          id: 'event_types',
          label: 'Event Types to Track',
          type: 'checkbox',
          options: ['$exception', '$error', 'custom_error'],
          defaultValue: ['$exception', '$error'],
          helpText: 'Select which event types should trigger feedback creation',
        },
      ],
    },
    sentry: {
      name: 'Sentry',
      icon: '⚠️',
      description: 'Capture errors and performance issues',
      enabled: false,
      fields: [
        {
          id: 'webhook_secret',
          label: 'Webhook Secret',
          type: 'password',
          placeholder: 'Enter your Sentry webhook secret',
          helpText: 'Found in Sentry project settings → Integrations → Webhooks',
          required: true,
        },
        {
          id: 'environments',
          label: 'Environments',
          type: 'checkbox',
          options: ['production', 'staging', 'development'],
          defaultValue: ['production'],
          helpText: 'Only issues from selected environments will be processed',
        },
        {
          id: 'levels',
          label: 'Severity Levels',
          type: 'checkbox',
          options: ['fatal', 'error', 'warning'],
          defaultValue: ['fatal', 'error'],
          helpText: 'Minimum severity level to capture',
        },
      ],
    },
  });

  // Load initial enabled states from backend
  useEffect(() => {
    const loadIntegrationStates = async () => {
      try {
        const integrations = ['splunk', 'datadog', 'posthog', 'sentry'];
        const results = await Promise.allSettled(
          integrations.map(async (integration) => {
            const res = await fetch(`${BACKEND_URL}/config/${integration}/enabled?project_id=default`);
            if (res.ok) {
              const data = await res.json();
              return { integration, enabled: data.enabled };
            }
            return { integration, enabled: false };
          })
        );

        setIntegrationConfigs((prev) => {
          const updated = { ...prev };
          results.forEach((result) => {
            if (result.status === 'fulfilled') {
              const { integration, enabled } = result.value;
              if (updated[integration as keyof typeof updated]) {
                updated[integration as keyof typeof updated] = {
                  ...updated[integration as keyof typeof updated],
                  enabled,
                };
              }
            }
          });
          return updated;
        });
      } catch (error) {
        console.error('Failed to load integration states:', error);
      }
    };

    loadIntegrationStates();
  }, []);

  // Integration configurations
  const splunkConfig = integrationConfigs.splunk;
  const datadogConfig = integrationConfigs.datadog;
  const posthogConfig = integrationConfigs.posthog;
  const sentryConfig = integrationConfigs.sentry;

  // Handle tab changes with URL persistence
  const handleTabChange = (tab: 'monitoring' | 'analytics') => {
    setActiveTab(tab);
    router.replace(`/settings/integrations?tab=${tab}`, { scroll: false });
  };

  // Toggle handlers for each integration
  const handleSplunkToggle = async (enabled: boolean) => {
    try {
      const res = await fetch(`${BACKEND_URL}/config/splunk/enabled?project_id=default`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled }),
      });
      if (!res.ok) throw new Error('Failed to update Splunk status');

      setIntegrationConfigs((prev) => ({
        ...prev,
        splunk: { ...prev.splunk, enabled },
      }));
    } catch (error) {
      console.error('Failed to toggle Splunk:', error);
      throw error;
    }
  };

  const handleDatadogToggle = async (enabled: boolean) => {
    try {
      const res = await fetch(`${BACKEND_URL}/config/datadog/enabled?project_id=default`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled }),
      });
      if (!res.ok) throw new Error('Failed to update Datadog status');

      setIntegrationConfigs((prev) => ({
        ...prev,
        datadog: { ...prev.datadog, enabled },
      }));
    } catch (error) {
      console.error('Failed to toggle Datadog:', error);
      throw error;
    }
  };

  const handlePostHogToggle = async (enabled: boolean) => {
    try {
      const res = await fetch(`${BACKEND_URL}/config/posthog/enabled?project_id=default`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled }),
      });
      if (!res.ok) throw new Error('Failed to update PostHog status');

      setIntegrationConfigs((prev) => ({
        ...prev,
        posthog: { ...prev.posthog, enabled },
      }));
    } catch (error) {
      console.error('Failed to toggle PostHog:', error);
      throw error;
    }
  };

  const handleSentryToggle = async (enabled: boolean) => {
    try {
      const res = await fetch(`${BACKEND_URL}/config/sentry/enabled?project_id=default`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled }),
      });
      if (!res.ok) throw new Error('Failed to update Sentry status');

      setIntegrationConfigs((prev) => ({
        ...prev,
        sentry: { ...prev.sentry, enabled },
      }));
    } catch (error) {
      console.error('Failed to toggle Sentry:', error);
      throw error;
    }
  };

  // Save handlers for each integration
  const handleSplunkSave = async (data: Record<string, any>) => {
    // Save token
    if (data.webhook_token) {
      const tokenRes = await fetch(`${BACKEND_URL}/config/splunk/token`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: 'default', // TODO: Get from session
          token: data.webhook_token
        }),
      });
      if (!tokenRes.ok) throw new Error('Failed to save webhook token');
    }

    // Save allowed searches
    if (data.allowed_searches) {
      const searches = data.allowed_searches
        .split('\n')
        .map((s: string) => s.trim())
        .filter(Boolean);
      const searchesRes = await fetch(`${BACKEND_URL}/config/splunk/searches`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: 'default',
          searches
        }),
      });
      if (!searchesRes.ok) throw new Error('Failed to save allowed searches');
    }
  };

  const handleDatadogSave = async (data: Record<string, any>) => {
    // Save webhook secret
    if (data.webhook_secret) {
      const secretRes = await fetch(`${BACKEND_URL}/config/datadog/secret`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: 'default',
          secret: data.webhook_secret
        }),
      });
      if (!secretRes.ok) throw new Error('Failed to save webhook secret');
    }

    // Save allowed monitors
    if (data.allowed_monitors) {
      const monitorsRes = await fetch(`${BACKEND_URL}/config/datadog/monitors`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: 'default',
          monitors: data.allowed_monitors
        }),
      });
      if (!monitorsRes.ok) throw new Error('Failed to save allowed monitors');
    }
  };

  const handlePostHogSave = async (data: Record<string, any>) => {
    const eventsRes = await fetch(`${BACKEND_URL}/config/posthog/events`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        project_id: 'default',
        event_types: data.event_types || []
      }),
    });
    if (!eventsRes.ok) throw new Error('Failed to save event types');
  };

  const handleSentrySave = async (data: Record<string, any>) => {
    // Save webhook secret
    if (data.webhook_secret) {
      const secretRes = await fetch(`${BACKEND_URL}/config/sentry/secret`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: 'default',
          secret: data.webhook_secret
        }),
      });
      if (!secretRes.ok) throw new Error('Failed to save webhook secret');
    }

    // Save environments
    if (data.environments) {
      const envsRes = await fetch(`${BACKEND_URL}/config/sentry/environments`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: 'default',
          environments: data.environments
        }),
      });
      if (!envsRes.ok) throw new Error('Failed to save environments');
    }

    // Save levels
    if (data.levels) {
      const levelsRes = await fetch(`${BACKEND_URL}/config/sentry/levels`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: 'default',
          levels: data.levels
        }),
      });
      if (!levelsRes.ok) throw new Error('Failed to save severity levels');
    }
  };

  const monitoringIntegrations = [
    { config: splunkConfig, onSave: handleSplunkSave, onToggle: handleSplunkToggle },
    { config: datadogConfig, onSave: handleDatadogSave, onToggle: handleDatadogToggle },
  ];

  const analyticsIntegrations = [
    { config: posthogConfig, onSave: handlePostHogSave, onToggle: handlePostHogToggle },
    { config: sentryConfig, onSave: handleSentrySave, onToggle: handleSentryToggle },
  ];

  return (
    <div className="min-h-screen">
      {/* Hero Section */}
      <div className="relative overflow-hidden border-b border-white/5 bg-gradient-to-b from-black via-black/95 to-transparent">
        {/* Animated background gradient */}
        <div className="pointer-events-none absolute -top-24 left-1/2 -translate-x-1/2 h-96 w-[800px] rounded-full bg-emerald-500/10 blur-[120px] opacity-60 animate-pulse" />

        <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 mb-6">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
            </span>
            <span className="text-xs font-medium text-emerald-300">Configuration</span>
          </div>

          <h1 className="text-4xl sm:text-5xl font-bold text-white mb-4">
            <span className="bg-gradient-to-r from-white via-emerald-200 to-emerald-400 bg-clip-text text-transparent">
              Integration Settings
            </span>
          </h1>

          <p className="text-lg text-slate-400 max-w-2xl leading-relaxed font-light">
            Connect your monitoring and analytics tools to automatically ingest feedback and trigger
            the self-healing dev loop. Configure webhooks, filters, and authentication below.
          </p>

          {/* Tab Navigation */}
          <div className="mt-8 flex items-center gap-2 border-b border-white/10 pb-0">
            <button
              onClick={() => handleTabChange('monitoring')}
              className={`px-6 py-3 text-sm font-medium border-b-2 transition-all ${
                activeTab === 'monitoring'
                  ? 'border-emerald-500 text-emerald-300'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <span className="flex items-center gap-2">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
                </svg>
                Monitoring
              </span>
            </button>
            <button
              onClick={() => handleTabChange('analytics')}
              className={`px-6 py-3 text-sm font-medium border-b-2 transition-all ${
                activeTab === 'analytics'
                  ? 'border-emerald-500 text-emerald-300'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <span className="flex items-center gap-2">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="12" y1="20" x2="12" y2="10" />
                  <line x1="18" y1="20" x2="18" y2="4" />
                  <line x1="6" y1="20" x2="6" y2="16" />
                </svg>
                Analytics
              </span>
            </button>
          </div>
        </div>
      </div>

      {/* Integration Cards Grid */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {activeTab === 'monitoring' &&
            monitoringIntegrations.map((integration, idx) => (
              <IntegrationCard
                key={integration.config.name}
                config={integration.config}
                onSave={integration.onSave}
                onToggle={integration.onToggle}
              />
            ))}

          {activeTab === 'analytics' &&
            analyticsIntegrations.map((integration, idx) => (
              <IntegrationCard
                key={integration.config.name}
                config={integration.config}
                onSave={integration.onSave}
                onToggle={integration.onToggle}
              />
            ))}
        </div>

        {/* Documentation Footer */}
        <div className="mt-16 border-t border-white/10 pt-8">
          <div className="bg-gradient-to-br from-black/40 via-black/20 to-black/40 border border-white/10 rounded-2xl p-8 backdrop-blur-sm">
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 rounded-lg bg-emerald-500/20 border border-emerald-500/30 flex items-center justify-center text-emerald-300 flex-shrink-0">
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="10" />
                  <line x1="12" y1="16" x2="12" y2="12" />
                  <line x1="12" y1="8" x2="12.01" y2="8" />
                </svg>
              </div>
              <div>
                <h4 className="text-lg font-semibold text-white mb-2">Need help configuring webhooks?</h4>
                <p className="text-sm text-slate-400 leading-relaxed mb-4">
                  Each integration requires webhook configuration on the source platform. Check out our
                  documentation for step-by-step setup guides for each tool.
                </p>
                <a
                  href="https://github.com/altock/soulcaster#integrations"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 text-sm font-medium text-emerald-300 hover:text-emerald-200 transition-colors"
                >
                  View Documentation
                  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                    <polyline points="15 3 21 3 21 9" />
                    <line x1="10" y1="14" x2="21" y2="3" />
                  </svg>
                </a>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
