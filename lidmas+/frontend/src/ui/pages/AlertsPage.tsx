import { useEffect, useState } from "react";

import { useJobs, useProviders, useRuns } from "../../api/hooks";
import type { Job, Provider, Run } from "../../api/types";
import { useDataMode } from "../../data/dataMode";
import { gkpAlertRules, gkpAlerts } from "../../data/gkpFixtures";

type AlertSeverity = "critical" | "warning" | "info";
type AlertStatus = "open" | "acknowledged" | "resolved" | "suppressed";
type AlertCategory = "provider" | "jobs" | "runs" | "quality" | "capacity" | "system";
type AlertsTab = "active" | "history" | "rules" | "notifications";
type RuleChannel = "pagerduty" | "slack" | "email";

interface AlertRecord {
  id: string;
  title: string;
  severity: AlertSeverity;
  category: AlertCategory;
  summary: string;
  impact: string;
  source: string;
  suggestedAction: string;
  triggeredAtMs: number;
}

interface AlertRule {
  id: number;
  name: string;
  condition: string;
  severity: AlertSeverity;
  channel: RuleChannel;
  enabled: boolean;
}

interface TimelineEvent {
  id: string;
  alertId: string;
  action: "acknowledged" | "resolved" | "suppressed" | "escalated" | "reopened" | "rule_updated";
  atMs: number;
  note: string;
}

interface NotificationPreferences {
  pagerduty: boolean;
  slack: boolean;
  email: boolean;
  sms: boolean;
  quietHoursEnabled: boolean;
  quietHoursStart: string;
  quietHoursEnd: string;
  digestCadence: "5m" | "15m" | "1h";
}

const API_RULES: AlertRule[] = [
  {
    id: 1,
    name: "Provider Redundancy",
    condition: "Trigger when configured providers drop below 2",
    severity: "warning",
    channel: "pagerduty",
    enabled: true,
  },
  {
    id: 2,
    name: "Job Failure Rate Spike",
    condition: "Trigger when failed jobs exceed 5% in rolling 1 hour window",
    severity: "critical",
    channel: "pagerduty",
    enabled: true,
  },
  {
    id: 3,
    name: "Run Warning Rate",
    condition: "Trigger when warning_rate exceeds 0.15 for active runs",
    severity: "warning",
    channel: "slack",
    enabled: true,
  },
  {
    id: 4,
    name: "Queue Backlog",
    condition: "Trigger when queued jobs remain above 3 for 10 minutes",
    severity: "warning",
    channel: "email",
    enabled: false,
  },
];

const DEFAULT_NOTIFICATION_PREFERENCES: NotificationPreferences = {
  pagerduty: true,
  slack: true,
  email: true,
  sms: false,
  quietHoursEnabled: false,
  quietHoursStart: "22:00",
  quietHoursEnd: "06:00",
  digestCadence: "15m",
};

const OWNERS = ["Unassigned", "Platform SRE", "Provider Ops", "Decoder Team", "Security Response"];

function parseTimestampToMs(value: string | null | undefined): number {
  if (!value) {
    return 0;
  }
  const first = Date.parse(value);
  if (!Number.isNaN(first)) {
    return first;
  }
  if (value.includes(" ")) {
    const normalized = value.replace(" ", "T");
    const second = Date.parse(normalized);
    if (!Number.isNaN(second)) {
      return second;
    }
  }
  return 0;
}

function formatUtcDateTime(ms: number): string {
  if (ms <= 0) {
    return "unknown";
  }
  return new Date(ms).toISOString().replace("T", " ").replace("Z", " UTC");
}

function formatRelativeAge(ms: number): string {
  if (ms <= 0) {
    return "unknown";
  }
  const diff = Math.max(0, Date.now() - ms);
  const minutes = Math.round(diff / 60_000);
  if (minutes < 1) {
    return "just now";
  }
  if (minutes < 60) {
    return `${minutes}m ago`;
  }
  const hours = Math.round(minutes / 60);
  if (hours < 24) {
    return `${hours}h ago`;
  }
  return `${Math.round(hours / 24)}d ago`;
}

function severityRank(severity: AlertSeverity): number {
  if (severity === "critical") {
    return 3;
  }
  if (severity === "warning") {
    return 2;
  }
  return 1;
}

function statusRank(status: AlertStatus): number {
  if (status === "open") {
    return 4;
  }
  if (status === "acknowledged") {
    return 3;
  }
  if (status === "suppressed") {
    return 2;
  }
  return 1;
}

function newestUpdatedAtMs(items: Array<{ updated_at: string }>): number {
  let newest = 0;
  for (const item of items) {
    const parsed = parseTimestampToMs(item.updated_at);
    if (parsed > newest) {
      newest = parsed;
    }
  }
  return newest;
}

function inferCategoryFromTitle(title: string): AlertCategory {
  const lower = title.toLowerCase();
  if (lower.includes("provider")) {
    return "provider";
  }
  if (lower.includes("job")) {
    return "jobs";
  }
  if (lower.includes("run")) {
    return "runs";
  }
  if (lower.includes("warning")) {
    return "quality";
  }
  if (lower.includes("queue") || lower.includes("backlog")) {
    return "capacity";
  }
  return "system";
}

function inferRuleSeverity(name: string): AlertSeverity {
  const lower = name.toLowerCase();
  if (lower.includes("timeout") || lower.includes("failure")) {
    return "critical";
  }
  if (lower.includes("residual") || lower.includes("rate")) {
    return "warning";
  }
  return "info";
}

function inferRuleChannel(name: string): RuleChannel {
  const lower = name.toLowerCase();
  if (lower.includes("timeout") || lower.includes("failure")) {
    return "pagerduty";
  }
  if (lower.includes("residual") || lower.includes("warning")) {
    return "slack";
  }
  return "email";
}

function deriveMockRules(): AlertRule[] {
  return gkpAlertRules.map((rule) => ({
    id: rule.id,
    name: rule.name,
    condition: rule.condition,
    severity: inferRuleSeverity(rule.name),
    channel: inferRuleChannel(rule.name),
    enabled: rule.enabled,
  }));
}

function cloneRules(source: AlertRule[]): AlertRule[] {
  return source.map((rule) => ({ ...rule }));
}

function timestampFromMockTriggered(triggered: string): number {
  const minutesAgoMatch = triggered.match(/(\d+)\s*min\s*ago/i);
  if (minutesAgoMatch) {
    return Date.now() - Number(minutesAgoMatch[1]) * 60_000;
  }
  const hmMatch = triggered.match(/(\d{2}):(\d{2})/);
  if (hmMatch) {
    const now = new Date();
    const ts = Date.UTC(
      now.getUTCFullYear(),
      now.getUTCMonth(),
      now.getUTCDate(),
      Number(hmMatch[1]),
      Number(hmMatch[2]),
      0,
      0,
    );
    return ts;
  }
  return Date.now();
}

function deriveMockAlerts(): AlertRecord[] {
  return gkpAlerts
    .map((alert) => ({
      id: `mock-${alert.id}`,
      title: alert.title,
      severity: alert.level,
      category: inferCategoryFromTitle(alert.title),
      summary: alert.message,
      impact: alert.meta,
      source: "mock/gkp-alert-feed",
      suggestedAction:
        alert.level === "critical"
          ? "Escalate immediately and freeze risky workload transitions."
          : "Acknowledge and track through on-call queue.",
      triggeredAtMs: timestampFromMockTriggered(alert.triggered),
    }))
    .sort((a, b) => severityRank(b.severity) - severityRank(a.severity) || b.triggeredAtMs - a.triggeredAtMs);
}

function deriveApiAlerts(providers: Provider[], jobs: Job[], runs: Run[]): AlertRecord[] {
  const alerts: AlertRecord[] = [];
  const failedJobs = jobs.filter((job) => job.status === "failed" || job.status === "cancelled");
  const failedRuns = runs.filter((run) => run.status === "failed" || run.status === "cancelled");
  const queuedJobs = jobs.filter((job) => job.status === "queued");
  const highWarningRuns = runs.filter((run) => (run.metrics?.warning_rate ?? 0) > 0.15);

  if (providers.length === 0) {
    alerts.push({
      id: "provider.none",
      title: "No Providers Configured",
      severity: "critical",
      category: "provider",
      summary: "No providers are currently registered. Job dispatch is blocked.",
      impact: "Affected scope: all queued and future jobs",
      source: "api/providers",
      suggestedAction: "Register at least one healthy provider and run connectivity validation.",
      triggeredAtMs: Date.now(),
    });
  } else if (providers.length < 2) {
    alerts.push({
      id: "provider.low_redundancy",
      title: "Low Provider Redundancy",
      severity: "warning",
      category: "provider",
      summary: "Only one provider is configured. Any outage can stop active decode pipelines.",
      impact: `Configured providers: ${providers.length}`,
      source: "api/providers",
      suggestedAction: "Add standby provider capacity and enable automatic failover.",
      triggeredAtMs: newestUpdatedAtMs(providers),
    });
  }

  if (failedJobs.length > 0) {
    alerts.push({
      id: "jobs.failures",
      title: "Job Failures Detected",
      severity: failedJobs.length > 2 ? "critical" : "warning",
      category: "jobs",
      summary: `${failedJobs.length} jobs are in failed/cancelled state and need review.`,
      impact: `Failed jobs: ${failedJobs.length}/${jobs.length || 1}`,
      source: "api/jobs",
      suggestedAction: "Inspect failure reasons, restart recoverable jobs, and quarantine invalid datasets.",
      triggeredAtMs: newestUpdatedAtMs(failedJobs),
    });
  }

  if (failedRuns.length > 0) {
    alerts.push({
      id: "runs.failures",
      title: "Run Execution Failures",
      severity: "critical",
      category: "runs",
      summary: `${failedRuns.length} runs failed to complete and may have partial artifacts.`,
      impact: `Failed runs: ${failedRuns.length}/${runs.length || 1}`,
      source: "api/runs",
      suggestedAction: "Review decoder traces and replay affected run batches with guarded rollout.",
      triggeredAtMs: newestUpdatedAtMs(failedRuns),
    });
  }

  if (queuedJobs.length >= 3) {
    alerts.push({
      id: "capacity.queue_backlog",
      title: "Queue Backlog Rising",
      severity: "warning",
      category: "capacity",
      summary: `${queuedJobs.length} jobs remain queued and may breach latency objectives.`,
      impact: `Queued jobs: ${queuedJobs.length}`,
      source: "api/jobs",
      suggestedAction: "Scale workers or activate priority shedding on non-critical workloads.",
      triggeredAtMs: newestUpdatedAtMs(queuedJobs),
    });
  }

  if (highWarningRuns.length > 0) {
    alerts.push({
      id: "quality.warning_rate",
      title: "High Warning Rate",
      severity: "warning",
      category: "quality",
      summary: `${highWarningRuns.length} runs exceed warning_rate threshold (0.15).`,
      impact: `Top warning_rate: ${Math.max(...highWarningRuns.map((run) => run.metrics?.warning_rate ?? 0)).toFixed(3)}`,
      source: "api/runs/quality",
      suggestedAction: "Pause suspect decoder set and compare output integrity against baseline replay.",
      triggeredAtMs: newestUpdatedAtMs(highWarningRuns),
    });
  }

  if (alerts.length === 0) {
    alerts.push({
      id: "system.healthy",
      title: "No Active Incidents",
      severity: "info",
      category: "system",
      summary: "Provider, job, and run signals are currently within defined operating thresholds.",
      impact: "Status: healthy",
      source: "api/alerts/inference",
      suggestedAction: "Maintain monitoring cadence and keep current alert policy.",
      triggeredAtMs: Math.max(newestUpdatedAtMs(runs), newestUpdatedAtMs(jobs), newestUpdatedAtMs(providers)),
    });
  }

  return alerts
    .sort((a, b) => severityRank(b.severity) - severityRank(a.severity) || b.triggeredAtMs - a.triggeredAtMs)
    .slice(0, 24);
}

function statusText(status: AlertStatus): string {
  if (status === "acknowledged") {
    return "Acknowledged";
  }
  if (status === "resolved") {
    return "Resolved";
  }
  if (status === "suppressed") {
    return "Suppressed";
  }
  return "Open";
}

export function AlertsPage() {
  const [activeTab, setActiveTab] = useState<AlertsTab>("active");
  const [severityFilter, setSeverityFilter] = useState<"all" | AlertSeverity>("all");
  const [statusFilter, setStatusFilter] = useState<"all" | AlertStatus>("open");
  const [categoryFilter, setCategoryFilter] = useState<"all" | AlertCategory>("all");
  const [ownerFilter, setOwnerFilter] = useState<string>("all");
  const [searchTerm, setSearchTerm] = useState("");
  const [rulesSearch, setRulesSearch] = useState("");
  const [rules, setRules] = useState<AlertRule[]>(() => cloneRules(deriveMockRules()));
  const [alertStatusById, setAlertStatusById] = useState<Record<string, AlertStatus>>({});
  const [alertOwnerById, setAlertOwnerById] = useState<Record<string, string>>({});
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [notificationPreferences, setNotificationPreferences] = useState<NotificationPreferences>(
    DEFAULT_NOTIFICATION_PREFERENCES,
  );

  const { isApi, isMock, systemOff, systemArmed } = useDataMode();
  const apiEnabled = isApi && !systemOff && systemArmed;

  const providersQuery = useProviders({ enabled: apiEnabled });
  const jobsQuery = useJobs({ enabled: apiEnabled });
  const runsQuery = useRuns({ enabled: apiEnabled });

  const providers = systemOff ? [] : providersQuery.data ?? [];
  const jobs = systemOff ? [] : jobsQuery.data ?? [];
  const runs = systemOff ? [] : runsQuery.data ?? [];
  const hasApiWarning = apiEnabled && (providersQuery.isError || jobsQuery.isError || runsQuery.isError);
  const isApiLoading = apiEnabled && (providersQuery.isLoading || jobsQuery.isLoading || runsQuery.isLoading);

  const alertFeed = systemOff ? [] : isMock ? deriveMockAlerts() : hasApiWarning ? [] : deriveApiAlerts(providers, jobs, runs);
  const alertFeedSignature = alertFeed.map((alert) => alert.id).join("|");

  useEffect(() => {
    setRules(cloneRules(isMock ? deriveMockRules() : API_RULES));
  }, [isMock]);

  useEffect(() => {
    setAlertStatusById((previous) => {
      const next: Record<string, AlertStatus> = {};
      for (const alert of alertFeed) {
        next[alert.id] = previous[alert.id] ?? "open";
      }
      return next;
    });
    setAlertOwnerById((previous) => {
      const next: Record<string, string> = {};
      for (const alert of alertFeed) {
        next[alert.id] = previous[alert.id] ?? "Unassigned";
      }
      return next;
    });
  }, [alertFeedSignature]);

  const alertQueue = alertFeed.map((alert) => ({
    ...alert,
    status: alertStatusById[alert.id] ?? "open",
    owner: alertOwnerById[alert.id] ?? "Unassigned",
  }));

  const normalizedSearch = searchTerm.trim().toLowerCase();
  const filteredAlerts = alertQueue
    .filter((alert) => (severityFilter === "all" ? true : alert.severity === severityFilter))
    .filter((alert) => (statusFilter === "all" ? true : alert.status === statusFilter))
    .filter((alert) => (categoryFilter === "all" ? true : alert.category === categoryFilter))
    .filter((alert) => (ownerFilter === "all" ? true : alert.owner === ownerFilter))
    .filter((alert) => {
      if (normalizedSearch.length === 0) {
        return true;
      }
      const haystack = `${alert.title} ${alert.summary} ${alert.impact} ${alert.source}`.toLowerCase();
      return haystack.includes(normalizedSearch);
    })
    .sort(
      (a, b) =>
        severityRank(b.severity) - severityRank(a.severity) ||
        statusRank(b.status) - statusRank(a.status) ||
        b.triggeredAtMs - a.triggeredAtMs,
    );

  const criticalOpenCount = alertQueue.filter((alert) => alert.severity === "critical" && alert.status === "open").length;
  const warningOpenCount = alertQueue.filter((alert) => alert.severity === "warning" && alert.status === "open").length;
  const unresolvedCount = alertQueue.filter((alert) => alert.status === "open" || alert.status === "acknowledged").length;
  const resolvedCount = alertQueue.filter((alert) => alert.status === "resolved").length;
  const suppressedCount = alertQueue.filter((alert) => alert.status === "suppressed").length;
  const meanAgeMinutes =
    unresolvedCount === 0
      ? 0
      : Math.round(
          alertQueue
            .filter((alert) => alert.status === "open" || alert.status === "acknowledged")
            .reduce((sum, alert) => sum + Math.max(0, Date.now() - alert.triggeredAtMs), 0) /
            unresolvedCount /
            60_000,
        );

  const tabs: Array<{ id: AlertsTab; label: string }> = [
    { id: "active", label: `Incident Queue (${filteredAlerts.length})` },
    { id: "history", label: `History (${timeline.length})` },
    { id: "rules", label: `Rules (${rules.length})` },
    { id: "notifications", label: "Notification Policy" },
  ];

  const addTimelineEvent = (alertId: string, action: TimelineEvent["action"], note: string) => {
    const event: TimelineEvent = {
      id: `${alertId}-${action}-${Date.now()}`,
      alertId,
      action,
      atMs: Date.now(),
      note,
    };
    setTimeline((previous) => [event, ...previous].slice(0, 120));
  };

  const updateAlertStatus = (alertId: string, nextStatus: AlertStatus, action: TimelineEvent["action"], note: string) => {
    setAlertStatusById((previous) => ({ ...previous, [alertId]: nextStatus }));
    addTimelineEvent(alertId, action, note);
  };

  const applyBulkStatus = (nextStatus: AlertStatus, action: TimelineEvent["action"], note: string) => {
    const targetAlerts = filteredAlerts.filter((alert) =>
      nextStatus === "acknowledged"
        ? alert.status === "open"
        : alert.status === "open" || alert.status === "acknowledged",
    );
    if (targetAlerts.length === 0) {
      return;
    }
    setAlertStatusById((previous) => {
      const next = { ...previous };
      for (const alert of targetAlerts) {
        next[alert.id] = nextStatus;
      }
      return next;
    });
    for (const alert of targetAlerts) {
      addTimelineEvent(alert.id, action, `${note} (${targetAlerts.length} alerts in scope)`);
    }
  };

  const hasOnlyHealthyInfo =
    alertQueue.length === 1 && alertQueue[0].id === "system.healthy" && (statusFilter === "all" || statusFilter === "open");

  return (
    <>
      <div className="header">
        <h1>Observability</h1>
        <p>Operational alerting, incident response, and runtime risk tracking.</p>
      </div>

      <div className="alerts-kpi-grid">
        <article className="alerts-kpi-card">
          <span>Critical Open</span>
          <strong>{criticalOpenCount}</strong>
          <p>must-page incidents</p>
        </article>
        <article className="alerts-kpi-card">
          <span>Warning Open</span>
          <strong>{warningOpenCount}</strong>
          <p>degradation indicators</p>
        </article>
        <article className="alerts-kpi-card">
          <span>Unresolved</span>
          <strong>{unresolvedCount}</strong>
          <p>open + acknowledged</p>
        </article>
        <article className="alerts-kpi-card">
          <span>Resolved</span>
          <strong>{resolvedCount}</strong>
          <p>closed incidents</p>
        </article>
        <article className="alerts-kpi-card">
          <span>Suppressed</span>
          <strong>{suppressedCount}</strong>
          <p>noise-control suppressions</p>
        </article>
        <article className="alerts-kpi-card">
          <span>Mean Alert Age</span>
          <strong>{meanAgeMinutes}m</strong>
          <p>unresolved queue age</p>
        </article>
      </div>

      <div className="alerts-controls">
        <div className="alerts-filter-grid">
          <input
            type="text"
            className="search-box alerts-search-box"
            placeholder="Search incidents (provider, timeout, warning_rate...)"
            value={searchTerm}
            onChange={(event) => setSearchTerm(event.target.value)}
          />
          <select
            className="alerts-select"
            value={severityFilter}
            onChange={(event) => setSeverityFilter(event.target.value as "all" | AlertSeverity)}
          >
            <option value="all">All severities</option>
            <option value="critical">Critical</option>
            <option value="warning">Warning</option>
            <option value="info">Info</option>
          </select>
          <select
            className="alerts-select"
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value as "all" | AlertStatus)}
          >
            <option value="all">All statuses</option>
            <option value="open">Open</option>
            <option value="acknowledged">Acknowledged</option>
            <option value="resolved">Resolved</option>
            <option value="suppressed">Suppressed</option>
          </select>
          <select
            className="alerts-select"
            value={categoryFilter}
            onChange={(event) => setCategoryFilter(event.target.value as "all" | AlertCategory)}
          >
            <option value="all">All categories</option>
            <option value="provider">Provider</option>
            <option value="jobs">Jobs</option>
            <option value="runs">Runs</option>
            <option value="quality">Quality</option>
            <option value="capacity">Capacity</option>
            <option value="system">System</option>
          </select>
          <select
            className="alerts-select"
            value={ownerFilter}
            onChange={(event) => setOwnerFilter(event.target.value)}
          >
            <option value="all">All owners</option>
            {OWNERS.map((owner) => (
              <option key={owner} value={owner}>
                {owner}
              </option>
            ))}
          </select>
        </div>
        <div className="alerts-action-row">
          <button className="btn btn-secondary" onClick={() => applyBulkStatus("acknowledged", "acknowledged", "Bulk acknowledge")}>
            Acknowledge Visible
          </button>
          <button className="btn btn-secondary" onClick={() => applyBulkStatus("resolved", "resolved", "Bulk resolve")}>
            Resolve Visible
          </button>
          <button className="btn btn-primary" onClick={() => setActiveTab("rules")}>
            + Create Rule
          </button>
        </div>
      </div>

      <div className="tabs">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            className={`tab ${activeTab === tab.id ? "active" : ""}`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === "active" ? (
        <>
          {filteredAlerts.map((alert) => (
            <div key={alert.id} className={`alert-item ${alert.severity} alerts-status-${alert.status}`}>
              <div className="alert-header">
                <div>
                  <div className="alert-title">{alert.title}</div>
                  <div className="alerts-inline-meta">
                    <span className={`alert-badge ${alert.severity}`}>{alert.severity}</span>
                    <span className="alerts-status-pill">{statusText(alert.status)}</span>
                    <span className="alerts-category-pill">{alert.category}</span>
                  </div>
                </div>
                <div className="alerts-inline-right">
                  <span className="alerts-age">{formatRelativeAge(alert.triggeredAtMs)}</span>
                  <span className="alerts-source">{alert.source}</span>
                </div>
              </div>
              <div className="alert-body">{alert.summary}</div>
              <div className="alert-meta">
                <span>{alert.impact}</span>
                <span>{formatUtcDateTime(alert.triggeredAtMs)}</span>
              </div>
              <div className="alerts-recommendation">{alert.suggestedAction}</div>
              <div className="alert-actions">
                <button
                  className="btn-small"
                  onClick={() => updateAlertStatus(alert.id, "acknowledged", "acknowledged", "Alert acknowledged")}
                  disabled={alert.status !== "open"}
                >
                  Acknowledge
                </button>
                <button
                  className="btn-small"
                  onClick={() => updateAlertStatus(alert.id, "resolved", "resolved", "Alert resolved")}
                  disabled={alert.status === "resolved"}
                >
                  Resolve
                </button>
                <button
                  className="btn-small"
                  onClick={() => updateAlertStatus(alert.id, "suppressed", "suppressed", "Alert suppressed")}
                  disabled={alert.status === "suppressed"}
                >
                  Suppress
                </button>
                <button
                  className="btn-small"
                  onClick={() => addTimelineEvent(alert.id, "escalated", "Escalated to incident channel")}
                >
                  Escalate
                </button>
                <button
                  className="btn-small"
                  onClick={() => updateAlertStatus(alert.id, "open", "reopened", "Alert reopened")}
                  disabled={alert.status === "open"}
                >
                  Reopen
                </button>
                <select
                  className="alerts-owner-select"
                  value={alert.owner}
                  onChange={(event) => {
                    const nextOwner = event.target.value;
                    setAlertOwnerById((previous) => ({ ...previous, [alert.id]: nextOwner }));
                    addTimelineEvent(alert.id, "acknowledged", `Assigned to ${nextOwner}`);
                  }}
                >
                  {OWNERS.map((owner) => (
                    <option key={owner} value={owner}>
                      Owner: {owner}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          ))}

          {hasOnlyHealthyInfo ? (
            <div className="empty-card section-offset">
              <strong>No Active Incidents</strong>
              <p>Current runtime appears healthy under configured alert thresholds.</p>
            </div>
          ) : null}

          {hasApiWarning ? (
            <div className="empty-card section-offset">
              <strong>API Warning</strong>
              <p>One or more API resources failed to load. Alert status may be incomplete.</p>
            </div>
          ) : null}

          {!hasApiWarning && filteredAlerts.length === 0 ? (
            <div className="empty-card section-offset">
              <strong>{isApiLoading ? "Loading Incident Feed" : "No Alerts for Current Filters"}</strong>
              <p>
                {isApiLoading
                  ? "Collecting provider, job, and run signals from the API."
                  : "Try broadening severity/status filters or clear search terms."}
              </p>
            </div>
          ) : null}
        </>
      ) : null}

      {activeTab === "history" ? (
        <>
          <div className="alerts-history-summary">
            <span>Events recorded: {timeline.length}</span>
            <span>Resolved alerts: {resolvedCount}</span>
            <span>Suppressed alerts: {suppressedCount}</span>
          </div>
          <div className="alerts-timeline">
            {timeline.map((event) => (
              <div key={event.id} className="alerts-timeline-item">
                <div className="alerts-timeline-time">{formatUtcDateTime(event.atMs)}</div>
                <div className="alerts-timeline-body">
                  <strong>{event.action}</strong>
                  <p>
                    Alert: {event.alertId} · {event.note}
                  </p>
                </div>
              </div>
            ))}
            {timeline.length === 0 ? (
              <div className="empty-card">
                <strong>No Timeline Events Yet</strong>
                <p>Alert actions will appear here once incidents are acknowledged or resolved.</p>
              </div>
            ) : null}
          </div>
        </>
      ) : null}

      {activeTab === "rules" ? (
        <>
          <div className="alerts-rules-toolbar">
            <input
              type="text"
              className="search-box alerts-search-box"
              placeholder="Search rules by name or condition..."
              value={rulesSearch}
              onChange={(event) => setRulesSearch(event.target.value)}
            />
            <span>{rules.filter((rule) => rule.enabled).length} enabled</span>
          </div>
          {rules
            .filter((rule) => {
              const token = rulesSearch.trim().toLowerCase();
              if (token.length === 0) {
                return true;
              }
              return `${rule.name} ${rule.condition}`.toLowerCase().includes(token);
            })
            .map((rule) => (
              <div key={rule.id} className="rule-item">
                <div className="rule-info">
                  <div className="rule-name">{rule.name}</div>
                  <div className="rule-condition">{rule.condition}</div>
                  <div className="alerts-inline-meta">
                    <span className={`alert-badge ${rule.severity}`}>{rule.severity}</span>
                    <span className="alerts-category-pill">channel: {rule.channel}</span>
                  </div>
                </div>
                <div className="rule-actions-row">
                  <button
                    className="btn-small"
                    onClick={() => addTimelineEvent(`rule-${rule.id}`, "rule_updated", `Simulated rule ${rule.id}`)}
                  >
                    Simulate
                  </button>
                  <button
                    className={`toggle ${rule.enabled ? "active" : ""}`}
                    aria-label={`toggle ${rule.name}`}
                    onClick={() => {
                      setRules((existing) =>
                        existing.map((existingRule) =>
                          existingRule.id === rule.id
                            ? { ...existingRule, enabled: !existingRule.enabled }
                            : existingRule,
                        ),
                      );
                      addTimelineEvent(
                        `rule-${rule.id}`,
                        "rule_updated",
                        `${rule.name} ${rule.enabled ? "disabled" : "enabled"}`,
                      );
                    }}
                  >
                    <span />
                  </button>
                </div>
              </div>
            ))}
        </>
      ) : null}

      {activeTab === "notifications" ? (
        <div className="alerts-notify-grid">
          <div className="rule-item">
            <div className="rule-info">
              <div className="rule-name">Delivery Channels</div>
              <div className="rule-condition">Choose which channels receive incident notifications.</div>
            </div>
            <div className="alerts-channel-toggles">
              {(["pagerduty", "slack", "email", "sms"] as const).map((channel) => (
                <button
                  key={channel}
                  className={`btn-small ${notificationPreferences[channel] ? "alerts-btn-enabled" : ""}`}
                  onClick={() =>
                    setNotificationPreferences((previous) => ({
                      ...previous,
                      [channel]: !previous[channel],
                    }))
                  }
                >
                  {channel} {notificationPreferences[channel] ? "on" : "off"}
                </button>
              ))}
            </div>
          </div>
          <div className="rule-item">
            <div className="rule-info">
              <div className="rule-name">Quiet Hours</div>
              <div className="rule-condition">Suppress non-critical pages during scheduled quiet periods.</div>
            </div>
            <div className="alerts-quiet-hours">
              <button
                className={`btn-small ${notificationPreferences.quietHoursEnabled ? "alerts-btn-enabled" : ""}`}
                onClick={() =>
                  setNotificationPreferences((previous) => ({
                    ...previous,
                    quietHoursEnabled: !previous.quietHoursEnabled,
                  }))
                }
              >
                Quiet Hours {notificationPreferences.quietHoursEnabled ? "On" : "Off"}
              </button>
              <input
                type="time"
                className="alerts-select"
                value={notificationPreferences.quietHoursStart}
                onChange={(event) =>
                  setNotificationPreferences((previous) => ({
                    ...previous,
                    quietHoursStart: event.target.value,
                  }))
                }
              />
              <input
                type="time"
                className="alerts-select"
                value={notificationPreferences.quietHoursEnd}
                onChange={(event) =>
                  setNotificationPreferences((previous) => ({
                    ...previous,
                    quietHoursEnd: event.target.value,
                  }))
                }
              />
            </div>
          </div>
          <div className="rule-item">
            <div className="rule-info">
              <div className="rule-name">Digest Cadence</div>
              <div className="rule-condition">Batch low-priority updates to reduce noise during stable periods.</div>
            </div>
            <div className="alerts-quiet-hours">
              <select
                className="alerts-select"
                value={notificationPreferences.digestCadence}
                onChange={(event) =>
                  setNotificationPreferences((previous) => ({
                    ...previous,
                    digestCadence: event.target.value as NotificationPreferences["digestCadence"],
                  }))
                }
              >
                <option value="5m">Every 5 minutes</option>
                <option value="15m">Every 15 minutes</option>
                <option value="1h">Hourly</option>
              </select>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
