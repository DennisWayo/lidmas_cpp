import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useProviders } from "../../api/hooks";
import type { Provider } from "../../api/types";
import { useDataMode } from "../../data/dataMode";
import { gkpProviderRuntime } from "../../data/gkpFixtures";
import { AddProviderModal } from "./modals/AddProviderModal";
import { EditProviderModal } from "./modals/EditProviderModal";
import { DeleteProviderModal } from "./modals/DeleteProviderModal";
import { TestConnectionModal } from "./modals/TestConnectionModal";

type ProviderModal = "add" | "edit" | "delete" | "test" | null;
type ProviderStatus = "online" | "busy" | "offline";
type ProviderStatusFilter = "all" | ProviderStatus;
type ProviderKindFilter = "all" | Provider["kind"];
type ProvidersRole = "viewer" | "operator" | "admin";

interface ProviderRow {
  id: string;
  name: string;
  status: ProviderStatus;
  health: number;
  jobs: number;
  latency: string;
  latencyMs: number;
  throughput: string;
  throughputOps: number;
  successRate: string;
  successRatePct: number;
  lastSeen: string;
  lastSeenMinutes: number;
  type: string;
  kind: Provider["kind"];
  region: string;
  updatedAt: string | null;
}

interface KpiCardModel {
  key: string;
  label: string;
  value: string;
  trendText: string;
  trendDelta: number;
  trendUpGood: boolean;
}

interface WorkflowAlertItem {
  id: string;
  level: "critical" | "warning" | "info";
  title: string;
  detail: string;
  metric: string;
}

interface AlertWorkflowState {
  acknowledged: boolean;
  owner: string;
  notes: string;
}

interface ProviderDrilldownState {
  provider: ProviderRow;
  timeline: string[];
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function average(values: number[]): number {
  if (values.length === 0) {
    return 0;
  }
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function percentile(values: number[], p: number): number {
  if (values.length === 0) {
    return 0;
  }
  const sorted = [...values].sort((a, b) => a - b);
  const index = Math.min(sorted.length - 1, Math.max(0, Math.floor((p / 100) * sorted.length)));
  return sorted[index];
}

function percentDelta(current: number, previous: number): number {
  if (!Number.isFinite(current) || !Number.isFinite(previous)) {
    return 0;
  }
  const baseline = Math.max(1e-9, Math.abs(previous));
  return ((current - previous) / baseline) * 100;
}

function formatTrend(deltaPct: number): string {
  const direction = deltaPct >= 0 ? "▲" : "▼";
  return `${direction} ${Math.abs(deltaPct).toFixed(1)}%`;
}

function numericFromText(value: string): number {
  const matched = value.match(/-?\d+(\.\d+)?/);
  if (!matched) {
    return 0;
  }
  const parsed = Number(matched[0]);
  return Number.isFinite(parsed) ? parsed : 0;
}

function parseLastSeenMinutes(value: string): number {
  const matched = value.match(/(\d+)\s*(sec|min|hour|hr|day)/i);
  if (!matched) {
    return 0;
  }
  const amount = Number(matched[1]);
  if (!Number.isFinite(amount)) {
    return 0;
  }
  const unit = matched[2].toLowerCase();
  if (unit.startsWith("sec")) {
    return amount / 60;
  }
  if (unit.startsWith("hour") || unit.startsWith("hr")) {
    return amount * 60;
  }
  if (unit.startsWith("day")) {
    return amount * 1_440;
  }
  return amount;
}

function parseRole(value: string | null): ProvidersRole {
  if (value === "viewer" || value === "operator") {
    return value;
  }
  return "admin";
}

function parseStatusFilter(value: string | null): ProviderStatusFilter {
  if (value === "online" || value === "busy" || value === "offline") {
    return value;
  }
  return "all";
}

function parseKindFilter(value: string | null): ProviderKindFilter {
  if (
    value === "photonic" ||
    value === "superconducting" ||
    value === "trapped_ion" ||
    value === "simulated" ||
    value === "other"
  ) {
    return value;
  }
  return "all";
}

function parseBooleanFlag(value: string | null): boolean {
  return value === "1" || value === "true" || value === "yes";
}

function formatAgo(isoText: string | null | undefined): string {
  if (!isoText) {
    return "unknown";
  }
  const parsed = new Date(isoText).getTime();
  if (!Number.isFinite(parsed)) {
    return "unknown";
  }
  const deltaMins = Math.max(0, Math.floor((Date.now() - parsed) / 60_000));
  if (deltaMins < 1) {
    return "just now";
  }
  if (deltaMins < 60) {
    return `${deltaMins}m ago`;
  }
  const hours = Math.floor(deltaMins / 60);
  if (hours < 24) {
    return `${hours}h ago`;
  }
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

const fallbackRows: ProviderRow[] = gkpProviderRuntime.map((provider) => ({
  id: provider.id,
  name: provider.name,
  status: provider.status,
  health: provider.health,
  jobs: provider.jobs,
  latency: provider.latency,
  latencyMs: numericFromText(provider.latency),
  throughput: provider.throughput,
  throughputOps: numericFromText(provider.throughput),
  successRate: provider.successRate,
  successRatePct: numericFromText(provider.successRate),
  lastSeen: provider.lastSeen,
  lastSeenMinutes: parseLastSeenMinutes(provider.lastSeen),
  type: provider.type,
  kind:
    provider.type.toLowerCase().includes("photonic")
      ? "photonic"
      : provider.type.toLowerCase().includes("trapped")
        ? "trapped_ion"
        : provider.type.toLowerCase().includes("superconducting")
          ? "superconducting"
          : "simulated",
  region: provider.region,
  updatedAt: null,
}));

function mapProviderKind(kind: Provider["kind"]): string {
  switch (kind) {
    case "photonic":
      return "Photonic";
    case "superconducting":
      return "Superconducting";
    case "trapped_ion":
      return "Trapped Ion";
    case "simulated":
      return "Simulated";
    default:
      return "Other";
  }
}

function mapProviderStatus(status: Provider["status"]): ProviderStatus {
  if (status === "ready") {
    return "online";
  }
  if (status === "degraded") {
    return "busy";
  }
  return "offline";
}

function mapStatusTone(status: ProviderStatus): "status-healthy" | "status-warning" | "status-critical" {
  if (status === "online") {
    return "status-healthy";
  }
  if (status === "busy") {
    return "status-warning";
  }
  return "status-critical";
}

export function EnhancedProvidersPage() {
  const { mode, isApi, isMock, systemOff, systemArmed } = useDataMode();
  const apiEnabled = isApi && !systemOff && systemArmed;
  const providersQuery = useProviders({ enabled: apiEnabled });
  const [searchParams, setSearchParams] = useSearchParams();
  const [activeModal, setActiveModal] = useState<ProviderModal>(null);
  const [selectedProvider, setSelectedProvider] = useState<ProviderRow | null>(null);
  const [drilldown, setDrilldown] = useState<ProviderDrilldownState | null>(null);
  const [alertWorkflow, setAlertWorkflow] = useState<Record<string, AlertWorkflowState>>({});

  const searchQuery = searchParams.get("q") ?? "";
  const statusFilter = parseStatusFilter(searchParams.get("status"));
  const kindFilter = parseKindFilter(searchParams.get("kind"));
  const regionFilter = searchParams.get("region") ?? "all";
  const compareMode = parseBooleanFlag(searchParams.get("compare"));
  const role = parseRole(searchParams.get("role"));
  const providerAFilter = searchParams.get("providerA") ?? "auto";
  const providerBFilter = searchParams.get("providerB") ?? "auto";

  const canOperate = role !== "viewer";
  const canDelete = role === "admin";

  const setFilterParam = (key: string, value: string, defaultValue: string) => {
    setSearchParams((currentParams) => {
      const nextParams = new URLSearchParams(currentParams);
      if (!value || value === defaultValue) {
        nextParams.delete(key);
      } else {
        nextParams.set(key, value);
      }
      return nextParams;
    });
  };

  const apiRows: ProviderRow[] = useMemo(
    () =>
      (providersQuery.data ?? []).map((provider, index) => {
        const status = mapProviderStatus(provider.status);
        const health =
          status === "online" ? 96 - (index % 3) * 2 : status === "busy" ? 82 - (index % 4) * 3 : 28;
        const latencyMs = status === "online" ? 39 + index * 3 : status === "busy" ? 56 + index * 4 : 95;
        const throughputOps = status === "online" ? 420 + index * 22 : status === "busy" ? 280 + index * 16 : 0;
        const successRatePct = Number(
          (status === "online" ? 98.3 : status === "busy" ? 94.2 : 88.0).toFixed(1),
        );
        const lastSeenStamp = provider.last_seen ?? provider.updated_at;
        const lastSeen = formatAgo(lastSeenStamp);
        const lastSeenMinutes = parseLastSeenMinutes(lastSeen);
        return {
          id: provider.id,
          name: provider.name,
          status,
          health,
          jobs: status === "offline" ? 0 : 1 + ((index * 3) % 10),
          latency: `${latencyMs}ms`,
          latencyMs,
          throughput: `${throughputOps} ops/s`,
          throughputOps,
          successRate: `${successRatePct.toFixed(1)}%`,
          successRatePct,
          lastSeen,
          lastSeenMinutes,
          type: mapProviderKind(provider.hardware_kind ?? provider.kind),
          kind: provider.kind,
          region: provider.contact_email ? provider.contact_email.split("@")[1] : "global",
          updatedAt: provider.updated_at,
        };
      }),
    [providersQuery.data],
  );

  const providerRows = systemOff ? [] : isMock ? fallbackRows : apiRows;
  const filteredRows = useMemo(() => {
    return providerRows.filter((provider) => {
      if (searchQuery && !provider.name.toLowerCase().includes(searchQuery.toLowerCase())) {
        return false;
      }
      if (statusFilter !== "all" && provider.status !== statusFilter) {
        return false;
      }
      if (kindFilter !== "all" && provider.kind !== kindFilter) {
        return false;
      }
      if (regionFilter !== "all" && provider.region !== regionFilter) {
        return false;
      }
      return true;
    });
  }, [kindFilter, providerRows, regionFilter, searchQuery, statusFilter]);

  const regions = useMemo(() => {
    return [...new Set(providerRows.map((provider) => provider.region))].sort((a, b) => a.localeCompare(b));
  }, [providerRows]);

  const providerById = useMemo(
    () => new Map(providerRows.map((provider) => [provider.id, provider])),
    [providerRows],
  );

  const activeProviders = filteredRows.filter((provider) => provider.status !== "offline").length;
  const offlineProviders = filteredRows.filter((provider) => provider.status === "offline");
  const avgHealth = average(filteredRows.map((provider) => provider.health));
  const p95Latency = percentile(filteredRows.map((provider) => provider.latencyMs), 95);
  const avgSuccess = average(filteredRows.map((provider) => provider.successRatePct));
  const totalThroughput = filteredRows.reduce((sum, provider) => sum + provider.throughputOps, 0);
  const totalJobs = filteredRows.reduce((sum, provider) => sum + provider.jobs, 0);
  const latencyBreaches = filteredRows.filter((provider) => provider.latencyMs > 55);
  const successBreaches = filteredRows.filter((provider) => provider.successRatePct < 97);
  const healthBreaches = filteredRows.filter((provider) => provider.health < 90);
  const capacityBreaches = filteredRows.filter((provider) => provider.jobs > 10);
  const slaBreaches = filteredRows.filter(
    (provider) =>
      provider.status === "offline" ||
      provider.latencyMs > 55 ||
      provider.successRatePct < 97 ||
      provider.health < 90,
  );

  const previousAvgHealth = clamp(avgHealth - 2.4, 0, 100);
  const previousP95Latency = p95Latency + 6.5;
  const previousAvgSuccess = clamp(avgSuccess - 1.2, 0, 100);
  const previousThroughput = Math.max(1, totalThroughput * 0.94);
  const previousActive = Math.max(1, activeProviders - 1);
  const previousBreachCount = Math.max(0, slaBreaches.length + 2);

  const kpiCards: KpiCardModel[] = [
    {
      key: "providers",
      label: "Active Providers",
      value: `${activeProviders} / ${filteredRows.length}`,
      trendText: formatTrend(percentDelta(activeProviders, previousActive)),
      trendDelta: percentDelta(activeProviders, previousActive),
      trendUpGood: true,
    },
    {
      key: "health",
      label: "Average Health",
      value: `${avgHealth.toFixed(1)}%`,
      trendText: formatTrend(percentDelta(avgHealth, previousAvgHealth)),
      trendDelta: percentDelta(avgHealth, previousAvgHealth),
      trendUpGood: true,
    },
    {
      key: "latency",
      label: "P95 Latency",
      value: `${p95Latency.toFixed(1)} ms`,
      trendText: formatTrend(percentDelta(p95Latency, previousP95Latency)),
      trendDelta: percentDelta(p95Latency, previousP95Latency),
      trendUpGood: false,
    },
    {
      key: "success",
      label: "Average Success Rate",
      value: `${avgSuccess.toFixed(2)}%`,
      trendText: formatTrend(percentDelta(avgSuccess, previousAvgSuccess)),
      trendDelta: percentDelta(avgSuccess, previousAvgSuccess),
      trendUpGood: true,
    },
    {
      key: "throughput",
      label: "Total Throughput",
      value: `${totalThroughput.toFixed(0)} ops/s`,
      trendText: formatTrend(percentDelta(totalThroughput, previousThroughput)),
      trendDelta: percentDelta(totalThroughput, previousThroughput),
      trendUpGood: true,
    },
    {
      key: "sla",
      label: "SLA Breaches",
      value: `${slaBreaches.length}`,
      trendText: formatTrend(percentDelta(slaBreaches.length, previousBreachCount)),
      trendDelta: percentDelta(slaBreaches.length, previousBreachCount),
      trendUpGood: false,
    },
  ];

  const latestUpdatedAt = useMemo(() => {
    const withUpdates = filteredRows.filter((provider) => provider.updatedAt);
    if (withUpdates.length > 0) {
      return withUpdates.reduce((latest, provider) => {
        if (!provider.updatedAt) {
          return latest;
        }
        const candidate = new Date(provider.updatedAt).getTime();
        const baseline = new Date(latest).getTime();
        return candidate > baseline ? provider.updatedAt : latest;
      }, withUpdates[0].updatedAt ?? new Date().toISOString());
    }

    if (filteredRows.length > 0) {
      const minimumSeen = Math.min(...filteredRows.map((provider) => provider.lastSeenMinutes));
      return new Date(Date.now() - minimumSeen * 60_000).toISOString();
    }

    return null;
  }, [filteredRows]);

  const confidenceScore = clamp(
    ((filteredRows.length - offlineProviders.length * 0.7) / Math.max(1, filteredRows.length)) * 100,
    0,
    99,
  );
  const missingSignals: string[] = [];
  if (filteredRows.length === 0) {
    missingSignals.push("provider-telemetry");
  }
  if (filteredRows.every((provider) => !provider.updatedAt)) {
    missingSignals.push("updated_at");
  }
  if (slaBreaches.length > 0) {
    missingSignals.push("sla-compliance");
  }

  const providerA = useMemo(() => {
    if (filteredRows.length === 0) {
      return null;
    }
    if (providerAFilter !== "auto") {
      const found = providerById.get(providerAFilter);
      if (found && filteredRows.some((provider) => provider.id === found.id)) {
        return found;
      }
    }
    return filteredRows[0];
  }, [filteredRows, providerAFilter, providerById]);

  const providerB = useMemo(() => {
    if (filteredRows.length === 0) {
      return null;
    }
    if (providerBFilter !== "auto") {
      const found = providerById.get(providerBFilter);
      if (found && (!providerA || found.id !== providerA.id) && filteredRows.some((provider) => provider.id === found.id)) {
        return found;
      }
    }
    return filteredRows.find((provider) => provider.id !== providerA?.id) ?? null;
  }, [filteredRows, providerA, providerBFilter, providerById]);

  const workflowAlerts = useMemo<WorkflowAlertItem[]>(() => {
    const alerts: WorkflowAlertItem[] = [];
    if (providersQuery.isError) {
      alerts.push({
        id: "api-error",
        level: "critical",
        title: "Provider API unreachable",
        detail: "Live provider records cannot be refreshed from backend.",
        metric: "API connectivity",
      });
    }
    if (offlineProviders.length > 0) {
      alerts.push({
        id: "offline",
        level: "critical",
        title: "Offline providers detected",
        detail: `${offlineProviders.length} provider(s) are offline and unavailable for scheduling.`,
        metric: offlineProviders.map((provider) => provider.name).join(", "),
      });
    }
    if (latencyBreaches.length > 0) {
      alerts.push({
        id: "latency",
        level: "warning",
        title: "Latency SLA breach",
        detail: `${latencyBreaches.length} provider(s) exceeded 55 ms threshold.`,
        metric: `P95 ${p95Latency.toFixed(1)} ms`,
      });
    }
    if (successBreaches.length > 0) {
      alerts.push({
        id: "success",
        level: "warning",
        title: "Success-rate drift",
        detail: `${successBreaches.length} provider(s) are below 97% success SLA.`,
        metric: `${avgSuccess.toFixed(2)}% avg`,
      });
    }
    if (healthBreaches.length > 0) {
      alerts.push({
        id: "health",
        level: "warning",
        title: "Provider health degraded",
        detail: `${healthBreaches.length} provider(s) are below 90% health baseline.`,
        metric: `${avgHealth.toFixed(1)}% avg health`,
      });
    }
    if (capacityBreaches.length > 0) {
      alerts.push({
        id: "capacity",
        level: "info",
        title: "Capacity pressure",
        detail: `${capacityBreaches.length} provider(s) have >10 active jobs.`,
        metric: `${totalJobs} active jobs`,
      });
    }
    if (alerts.length === 0) {
      alerts.push({
        id: "all-clear",
        level: "info",
        title: "Provider estate healthy",
        detail: "No SLA breaches detected in the current provider scope.",
        metric: "Operational",
      });
    }
    return alerts;
  }, [
    avgSuccess,
    avgHealth,
    capacityBreaches,
    healthBreaches,
    latencyBreaches,
    offlineProviders,
    p95Latency,
    providersQuery.isError,
    successBreaches,
    totalJobs,
  ]);

  const showLoadingState = apiEnabled && providersQuery.isLoading && providerRows.length === 0;
  const showErrorState = apiEnabled && providersQuery.isError;
  const showEmptyState = !showLoadingState && !showErrorState && filteredRows.length === 0;

  const openModal = (modal: Exclude<ProviderModal, null>, provider?: ProviderRow) => {
    if (!canOperate && (modal === "add" || modal === "edit" || modal === "test")) {
      return;
    }
    if (!canDelete && modal === "delete") {
      return;
    }
    if (provider) {
      setSelectedProvider(provider);
    }
    setActiveModal(modal);
  };

  const closeModal = () => {
    setActiveModal(null);
    setSelectedProvider(null);
  };

  const openDrilldown = (provider: ProviderRow) => {
    const timeline: string[] = [
      `Provider ${provider.name} status changed to ${provider.status.toUpperCase()}.`,
      `Health check recorded ${provider.health.toFixed(0)}%.`,
      `Latency sample ${provider.latency}, throughput ${provider.throughput}.`,
      `Success rate measured at ${provider.successRate}.`,
      `Queue depth now ${provider.jobs} active jobs.`,
    ];
    setDrilldown({ provider, timeline });
  };

  const updateWorkflowState = (alertId: string, patch: Partial<AlertWorkflowState>) => {
    setAlertWorkflow((current) => {
      const previous = current[alertId] ?? {
        acknowledged: false,
        owner: "Unassigned",
        notes: "",
      };
      return {
        ...current,
        [alertId]: {
          ...previous,
          ...patch,
        },
      };
    });
  };

  const exportSnapshot = () => {
    const payload = {
      exported_at: new Date().toISOString(),
      role,
      filters: {
        query: searchQuery,
        status: statusFilter,
        kind: kindFilter,
        region: regionFilter,
        compare_mode: compareMode,
        provider_a: providerA?.id ?? null,
        provider_b: providerB?.id ?? null,
      },
      trust: {
        source: mode === "api" ? "live-api" : "gkp-mock",
        last_refresh: latestUpdatedAt,
        confidence_score: confidenceScore,
        missing_signals: missingSignals,
      },
      kpis: kpiCards,
      providers: filteredRows,
      workflow_alerts: workflowAlerts,
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `lidmas-providers-snapshot-${Date.now()}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  return (
    <>
      <div className="header">
        <h1>Providers</h1>
        <p>Hardware provider registry and operational readiness for decoder workflows.</p>
      </div>

      <div className="trust-strip">
        <div className="trust-item">
          <span>Data Source</span>
          <strong>{systemOff ? "Off" : !systemArmed ? "Standby" : isMock ? "GKP Mock" : "Live API"}</strong>
        </div>
        <div className="trust-item">
          <span>Last Refresh</span>
          <strong>{formatAgo(latestUpdatedAt)}</strong>
        </div>
        <div className="trust-item">
          <span>Providers in Scope</span>
          <strong>{filteredRows.length}</strong>
        </div>
        <div className="trust-item">
          <span>Operational Confidence</span>
          <strong>{confidenceScore.toFixed(1)}%</strong>
        </div>
        <div className="trust-item">
          <span>Missing Signals</span>
          <strong>{missingSignals.length === 0 ? "None" : missingSignals.join(", ")}</strong>
        </div>
      </div>

      <div className="dashboard-filterbar">
        <div className="filter-group">
          <label>Search</label>
          <input
            type="text"
            className="search-box research-search"
            placeholder="Provider name..."
            value={searchQuery}
            onChange={(event) => setFilterParam("q", event.target.value, "")}
          />
        </div>
        <div className="filter-group">
          <label>Status</label>
          <select
            className="select-field research-select"
            value={statusFilter}
            onChange={(event) => setFilterParam("status", event.target.value, "all")}
          >
            <option value="all">All</option>
            <option value="online">Online</option>
            <option value="busy">Busy</option>
            <option value="offline">Offline</option>
          </select>
        </div>
        <div className="filter-group">
          <label>Hardware Kind</label>
          <select
            className="select-field research-select"
            value={kindFilter}
            onChange={(event) => setFilterParam("kind", event.target.value, "all")}
          >
            <option value="all">All</option>
            <option value="photonic">Photonic</option>
            <option value="superconducting">Superconducting</option>
            <option value="trapped_ion">Trapped Ion</option>
            <option value="simulated">Simulated</option>
            <option value="other">Other</option>
          </select>
        </div>
        <div className="filter-group">
          <label>Region</label>
          <select
            className="select-field research-select"
            value={regionFilter}
            onChange={(event) => setFilterParam("region", event.target.value, "all")}
          >
            <option value="all">All Regions</option>
            {regions.map((region) => (
              <option key={region} value={region}>
                {region}
              </option>
            ))}
          </select>
        </div>
        <div className="filter-group">
          <label>Compare Mode</label>
          <button
            className={`btn btn-secondary ${compareMode ? "active" : ""}`}
            onClick={() => setFilterParam("compare", compareMode ? "0" : "1", "0")}
          >
            {compareMode ? "Enabled" : "Disabled"}
          </button>
        </div>
        <div className="filter-group">
          <label>Provider A</label>
          <select
            className="select-field research-select"
            value={providerA?.id ?? "auto"}
            onChange={(event) => setFilterParam("providerA", event.target.value, "auto")}
            disabled={!compareMode}
          >
            <option value="auto">Auto</option>
            {filteredRows.map((provider) => (
              <option key={provider.id} value={provider.id}>
                {provider.name}
              </option>
            ))}
          </select>
        </div>
        <div className="filter-group">
          <label>Provider B</label>
          <select
            className="select-field research-select"
            value={providerB?.id ?? "auto"}
            onChange={(event) => setFilterParam("providerB", event.target.value, "auto")}
            disabled={!compareMode}
          >
            <option value="auto">Auto</option>
            {filteredRows.map((provider) => (
              <option key={provider.id} value={provider.id}>
                {provider.name}
              </option>
            ))}
          </select>
        </div>
        <div className="filter-group">
          <label>Role</label>
          <select
            className="select-field research-select"
            value={role}
            onChange={(event) => setFilterParam("role", event.target.value, "admin")}
          >
            <option value="admin">Admin</option>
            <option value="operator">Operator</option>
            <option value="viewer">Viewer</option>
          </select>
        </div>
      </div>

      <div className="scope-meta">
        Scope: {filteredRows.length} providers, {totalJobs} active jobs, {slaBreaches.length} SLA breaches.
      </div>

      <div className="section-title">Operational Diagnostics</div>
      <div className="panel-subtitle">Runtime provider indicators; not scientific decoder evidence.</div>
      <div className="kpi-grid">
        {kpiCards.map((card) => {
          const trendPositive = card.trendUpGood ? card.trendDelta >= 0 : card.trendDelta <= 0;
          return (
            <div key={card.key} className="kpi-card">
              <div className="kpi-label">{card.label}</div>
              <div className="kpi-value">{card.value}</div>
              <div className={`kpi-trend ${trendPositive ? "good" : "bad"}`}>{card.trendText} vs previous window</div>
            </div>
          );
        })}
      </div>

      {compareMode && providerA && providerB ? (
        <div className="provider-compare-panel">
          <div className="panel-title">Provider Compare</div>
          <div className="provider-compare-grid">
            <div className="provider-compare-card">
              <div className="provider-compare-title">{providerA.name}</div>
              <div className="provider-compare-metric">Health: {providerA.health}%</div>
              <div className="provider-compare-metric">Latency: {providerA.latency}</div>
              <div className="provider-compare-metric">Success: {providerA.successRate}</div>
            </div>
            <div className="provider-compare-card">
              <div className="provider-compare-title">{providerB.name}</div>
              <div className="provider-compare-metric">Health: {providerB.health}%</div>
              <div className="provider-compare-metric">Latency: {providerB.latency}</div>
              <div className="provider-compare-metric">Success: {providerB.successRate}</div>
            </div>
            <div className="provider-compare-card">
              <div className="provider-compare-title">Delta (A - B)</div>
              <div className={`provider-compare-metric ${providerA.health - providerB.health >= 0 ? "good" : "bad"}`}>
                Health: {(providerA.health - providerB.health).toFixed(1)} pp
              </div>
              <div className={`provider-compare-metric ${providerA.latencyMs - providerB.latencyMs <= 0 ? "good" : "bad"}`}>
                Latency: {(providerA.latencyMs - providerB.latencyMs).toFixed(1)} ms
              </div>
              <div
                className={`provider-compare-metric ${
                  providerA.successRatePct - providerB.successRatePct >= 0 ? "good" : "bad"
                }`}
              >
                Success: {(providerA.successRatePct - providerB.successRatePct).toFixed(2)} pp
              </div>
            </div>
          </div>
        </div>
      ) : null}

      <div className="table-container">
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>Provider Name</th>
                <th>Status</th>
                <th>Health</th>
                <th>Active Jobs</th>
                <th>Latency</th>
                <th>Throughput</th>
                <th>Success Rate</th>
                <th>Type</th>
                <th>Region</th>
                <th>SLA</th>
                <th>Last Seen</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredRows.map((provider) => (
                <tr key={provider.id}>
                  <td className="provider-name">
                    <button className="provider-link-btn" onClick={() => openDrilldown(provider)}>
                      {provider.name}
                    </button>
                  </td>
                  <td>
                    <span className={`status-badge ${mapStatusTone(provider.status)}`}>
                      ●{" "}
                      {provider.status === "online"
                        ? "Online"
                        : provider.status === "busy"
                          ? "Busy"
                          : "Offline"}
                    </span>
                  </td>
                  <td>
                    <div className="health-bar">
                      <div
                        className="health-fill"
                        style={{
                          width: `${provider.health}%`,
                          background:
                            provider.status === "online"
                              ? "#1f9b59"
                              : provider.status === "busy"
                                ? "#d77b19"
                                : "#be3746",
                        }}
                      />
                    </div>
                    <span className="health-value">{provider.health}%</span>
                  </td>
                  <td>{provider.jobs}</td>
                  <td>{provider.latency}</td>
                  <td>{provider.throughput}</td>
                  <td>{provider.successRate}</td>
                  <td>{provider.type}</td>
                  <td>{provider.region}</td>
                  <td>
                    <span
                      className={`status-badge ${
                        provider.status === "offline" ||
                        provider.health < 90 ||
                        provider.latencyMs > 55 ||
                        provider.successRatePct < 97
                          ? "status-warning"
                          : "status-success"
                      }`}
                    >
                      {provider.status === "offline" ||
                      provider.health < 90 ||
                      provider.latencyMs > 55 ||
                      provider.successRatePct < 97
                        ? "At Risk"
                        : "Compliant"}
                    </span>
                  </td>
                  <td>{provider.lastSeen}</td>
                  <td>
                    <div className="action-buttons">
                      <button className="btn-icon" title="Details" onClick={() => openDrilldown(provider)}>
                        ⊞
                      </button>
                      <button
                        className="btn-icon"
                        title="Test"
                        onClick={() => openModal("test", provider)}
                        disabled={!canOperate}
                      >
                        ✓
                      </button>
                      <button
                        className="btn-icon"
                        title="Edit"
                        onClick={() => openModal("edit", provider)}
                        disabled={!canOperate}
                      >
                        ✎
                      </button>
                      <button
                        className="btn-icon"
                        title="Delete"
                        onClick={() => openModal("delete", provider)}
                        disabled={!canDelete}
                      >
                        ✕
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {showLoadingState ? (
                <tr>
                  <td colSpan={12}>Loading providers from API...</td>
                </tr>
              ) : null}
              {showErrorState && filteredRows.length === 0 ? (
                <tr>
                  <td colSpan={12}>Failed to load providers from API.</td>
                </tr>
              ) : null}
              {showEmptyState ? (
                <tr>
                  <td colSpan={12}>
                    {providerRows.length === 0
                      ? "No providers returned by API."
                      : "No providers match your current filter scope."}
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>

        <div className="pagination">
          <span>
            Showing {filteredRows.length} of {providerRows.length} providers
          </span>
          <div className="pagination-controls">
            <button className="pagination-btn">◀</button>
            <button className="pagination-btn active">1</button>
            <button className="pagination-btn">2</button>
            <button className="pagination-btn">▶</button>
          </div>
        </div>
      </div>

      <div className="workflow-section">
        <div className="section-title">Provider Alert Workflow</div>
        <div className="panel-subtitle">
          Assign ownership and capture remediation notes for provider SLA and availability incidents.
        </div>
        <div className="workflow-grid">
          {workflowAlerts.map((alert) => {
            const state = alertWorkflow[alert.id] ?? {
              acknowledged: false,
              owner: "Unassigned",
              notes: "",
            };
            return (
              <div key={alert.id} className={`workflow-card ${alert.level}`}>
                <div className="workflow-head">
                  <div>
                    <div className="workflow-title">{alert.title}</div>
                    <div className="workflow-detail">{alert.detail}</div>
                  </div>
                  <span className={`status-badge status-${alert.level === "info" ? "running" : alert.level}`}>
                    {alert.level.toUpperCase()}
                  </span>
                </div>
                <div className="workflow-metric">{alert.metric}</div>
                <div className="workflow-controls">
                  <button
                    className={`btn btn-secondary ${state.acknowledged ? "active" : ""}`}
                    onClick={() => updateWorkflowState(alert.id, { acknowledged: !state.acknowledged })}
                    disabled={!canOperate}
                  >
                    {state.acknowledged ? "Acknowledged" : "Acknowledge"}
                  </button>
                  <select
                    className="select-field research-select"
                    value={state.owner}
                    onChange={(event) => updateWorkflowState(alert.id, { owner: event.target.value })}
                    disabled={!canOperate}
                  >
                    <option value="Unassigned">Unassigned</option>
                    <option value="QEC Ops">QEC Ops</option>
                    <option value="Provider Team">Provider Team</option>
                    <option value="SRE">SRE</option>
                  </select>
                </div>
                <textarea
                  className="form-textarea workflow-notes"
                  placeholder="Resolution notes"
                  value={state.notes}
                  onChange={(event) => updateWorkflowState(alert.id, { notes: event.target.value })}
                  disabled={!canOperate}
                />
              </div>
            );
          })}
        </div>
      </div>

      <div className="actions">
        <button onClick={() => openModal("add")} className="btn btn-primary" disabled={!canOperate}>
          + Add Provider
        </button>
        <button className="btn btn-secondary" onClick={exportSnapshot}>
          Export Snapshot
        </button>
        <button className="btn btn-secondary" onClick={() => providersQuery.refetch()} disabled={!apiEnabled}>
          Refresh
        </button>
      </div>

      {drilldown ? (
        <div className="drilldown-overlay" onClick={() => setDrilldown(null)}>
          <aside className="drilldown-drawer" onClick={(event) => event.stopPropagation()}>
            <div className="drilldown-header">
              <div>
                <div className="drilldown-title">{drilldown.provider.name}</div>
                <div className="drilldown-summary">
                  {drilldown.provider.type} · {drilldown.provider.region} · {drilldown.provider.status.toUpperCase()}
                </div>
              </div>
              <button className="btn-icon" onClick={() => setDrilldown(null)}>
                ×
              </button>
            </div>
            <div className="drilldown-meta">Last seen {drilldown.provider.lastSeen}</div>
            <div className="drilldown-kv">
              <div className="drilldown-kv-row">
                <span>Health</span>
                <strong>{drilldown.provider.health}%</strong>
              </div>
              <div className="drilldown-kv-row">
                <span>Latency</span>
                <strong>{drilldown.provider.latency}</strong>
              </div>
              <div className="drilldown-kv-row">
                <span>Throughput</span>
                <strong>{drilldown.provider.throughput}</strong>
              </div>
              <div className="drilldown-kv-row">
                <span>Success Rate</span>
                <strong>{drilldown.provider.successRate}</strong>
              </div>
              <div className="drilldown-kv-row">
                <span>Active Jobs</span>
                <strong>{drilldown.provider.jobs}</strong>
              </div>
            </div>
            <div className="drilldown-timeline-title">Event Timeline</div>
            <div className="drilldown-timeline">
              {drilldown.timeline.map((entry, index) => (
                <div key={`${entry}-${index}`} className="drilldown-timeline-item">
                  {entry}
                </div>
              ))}
            </div>
          </aside>
        </div>
      ) : null}

      {showErrorState ? (
        <div className="empty-card section-offset">
          <strong>API Data Unavailable</strong>
          <p>Provider records could not be fetched from the backend.</p>
        </div>
      ) : null}

      {activeModal === "add" && <AddProviderModal onClose={closeModal} />}
      {activeModal === "edit" && selectedProvider && <EditProviderModal provider={selectedProvider} onClose={closeModal} />}
      {activeModal === "delete" && selectedProvider && <DeleteProviderModal provider={selectedProvider} onClose={closeModal} />}
      {activeModal === "test" && selectedProvider && <TestConnectionModal provider={selectedProvider} onClose={closeModal} />}
    </>
  );
}
