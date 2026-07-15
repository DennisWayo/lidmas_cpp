import { useDeferredValue, useEffect, useRef, useState } from "react";

import { useJobs, useProviders, useRuns, useSystemLogScan } from "../../api/hooks";
import type {
  Job,
  LogSeverity as ScanSeverity,
  Provider,
  Run,
  SystemLogScanRule,
  SystemLogSuppression,
} from "../../api/types";
import { useDataMode } from "../../data/dataMode";
import { gkpLogs } from "../../data/gkpFixtures";

type LogLevel = "ERROR" | "WARN" | "INFO" | "SUCCESS";
type TimeWindow = "all" | "15m" | "1h" | "24h";
type SortOrder = "newest" | "oldest";
type ScanProfileKey = "standard" | "security" | "availability" | "compliance";
type ScanScope = "all" | "filtered";

interface ParsedLogEntry {
  id: string;
  timestamp: string;
  level: LogLevel;
  message: string;
  source: string;
  sortAt: number;
  searchText: string;
}

interface ScanProfile {
  label: string;
  description: string;
  customRules: SystemLogScanRule[];
  suppressions: SystemLogSuppression[];
  defaultMaxFindings: number;
}

const MAX_EXPORT_LINES = 10_000;
const AUTO_REFRESH_MS = 15_000;
const MIN_MAX_FINDINGS = 1;
const MAX_MAX_FINDINGS = 5_000;

const TIME_WINDOW_MS: Record<TimeWindow, number | null> = {
  all: null,
  "15m": 15 * 60 * 1_000,
  "1h": 60 * 60 * 1_000,
  "24h": 24 * 60 * 60 * 1_000,
};

const SCAN_PROFILES: Record<ScanProfileKey, ScanProfile> = {
  standard: {
    label: "Standard",
    description: "Balanced reliability scan for runtime, decoder quality, and operational stability.",
    customRules: [
      {
        id: "frontend.standard.failover",
        title: "Failover path exercised",
        pattern: "failover initiated",
        severity: "low",
        field: "message",
        tags: ["operations", "resilience"],
        recommendation: "Validate recovery latency and confirm no replay gaps after failover.",
      },
      {
        id: "frontend.standard.residual_spike",
        title: "Residual quality drift",
        pattern: "residual weight spike",
        severity: "medium",
        field: "message",
        tags: ["decoder", "quality"],
        recommendation: "Compare residual trend to baseline and quarantine unstable decoder window.",
      },
    ],
    suppressions: [{ pattern: "runtime snapshot received", field: "message" }],
    defaultMaxFindings: 100,
  },
  security: {
    label: "Security",
    description: "Focuses on credentials, authorization errors, and possible secret leakage patterns.",
    customRules: [
      {
        id: "frontend.security.jwt_exposure",
        title: "Bearer token exposed in log message",
        pattern: "bearer ",
        severity: "critical",
        field: "any",
        tags: ["security", "secrets"],
        recommendation: "Rotate exposed tokens and enforce redaction before serialization.",
      },
      {
        id: "frontend.security.authz_error",
        title: "Authorization denial pattern",
        pattern: "permission denied",
        severity: "high",
        field: "any",
        tags: ["security", "authz"],
        recommendation: "Audit RBAC policy and verify provider key scopes.",
      },
      {
        id: "frontend.security.privkey_hint",
        title: "Private key marker in logs",
        pattern: "-----begin",
        severity: "critical",
        field: "message",
        tags: ["security", "crypto"],
        recommendation: "Treat as key leak incident and revoke material immediately.",
      },
    ],
    suppressions: [],
    defaultMaxFindings: 150,
  },
  availability: {
    label: "Availability",
    description: "Targets timeout storms, provider degradation, and queue pressure indicators.",
    customRules: [
      {
        id: "frontend.availability.timeout",
        title: "Provider timeout burst",
        pattern: "timeout",
        severity: "high",
        field: "any",
        tags: ["availability", "provider"],
        recommendation: "Switch traffic to healthy provider pool and validate retry backoff.",
      },
      {
        id: "frontend.availability.backlog",
        title: "Queue backlog growth",
        pattern: "queue depth",
        severity: "medium",
        field: "message",
        tags: ["operations", "throughput"],
        recommendation: "Scale workers or apply traffic shaping to keep queue within SLA.",
      },
      {
        id: "frontend.availability.health_drop",
        title: "Provider health degradation",
        pattern: "health check failed",
        severity: "high",
        field: "message",
        tags: ["availability", "health-check"],
        recommendation: "Mark provider degraded and force health-gated scheduling.",
      },
    ],
    suppressions: [],
    defaultMaxFindings: 180,
  },
  compliance: {
    label: "Compliance",
    description: "Looks for compliance-sensitive content (PII-like strings and policy violations).",
    customRules: [
      {
        id: "frontend.compliance.pii_email",
        title: "Potential email-like identifier in logs",
        pattern: "@",
        severity: "medium",
        field: "message",
        tags: ["compliance", "pii"],
        recommendation: "Review data minimization policy and redact user identifiers in log pipeline.",
      },
      {
        id: "frontend.compliance.password_literal",
        title: "Password literal detected",
        pattern: "password=",
        severity: "high",
        field: "any",
        tags: ["compliance", "secrets"],
        recommendation: "Stop logging sensitive parameters and rotate affected credentials.",
      },
      {
        id: "frontend.compliance.token_literal",
        title: "Token literal detected",
        pattern: "api_key=",
        severity: "high",
        field: "any",
        tags: ["compliance", "secrets"],
        recommendation: "Apply irreversible masking for secrets before event persistence.",
      },
    ],
    suppressions: [{ pattern: "provider provider-", field: "message" }],
    defaultMaxFindings: 160,
  },
};

function formatScanVerdict(verdict: "pass" | "warn" | "critical"): string {
  if (verdict === "critical") {
    return "CRITICAL";
  }
  if (verdict === "warn") {
    return "WARN";
  }
  return "PASS";
}

function mapScanSeverityToLogLevel(severity: ScanSeverity): "error" | "warn" | "info" | "success" {
  if (severity === "critical" || severity === "high") {
    return "error";
  }
  if (severity === "medium") {
    return "warn";
  }
  if (severity === "low") {
    return "success";
  }
  return "info";
}

function mapScanVerdictToClassName(verdict: "pass" | "warn" | "critical"): string {
  if (verdict === "critical") {
    return "critical";
  }
  if (verdict === "warn") {
    return "warn";
  }
  return "pass";
}

function formatLogTimestamp(value: string | null | undefined): string {
  if (!value) {
    return "—";
  }
  const directFormat = /^\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}/.test(value);
  if (directFormat) {
    return value;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toISOString().replace("T", " ").replace("Z", "");
}

function timestampToMs(value: string | null | undefined): number {
  if (!value) {
    return 0;
  }
  const direct = Date.parse(value);
  if (!Number.isNaN(direct)) {
    return direct;
  }
  if (value.includes(" ")) {
    const isoLike = value.replace(" ", "T");
    const parsed = Date.parse(isoLike);
    if (!Number.isNaN(parsed)) {
      return parsed;
    }
  }
  return 0;
}

function mapJobLogLevel(status: Job["status"]): LogLevel {
  if (status === "completed") {
    return "SUCCESS";
  }
  if (status === "failed" || status === "cancelled") {
    return "ERROR";
  }
  if (status === "queued") {
    return "WARN";
  }
  return "INFO";
}

function mapRunLogLevel(status: Run["status"]): LogLevel {
  if (status === "finished") {
    return "SUCCESS";
  }
  if (status === "failed" || status === "cancelled") {
    return "ERROR";
  }
  return "INFO";
}

function buildEntry(id: string, timestamp: string, level: LogLevel, message: string, source: string, sortAt: number): ParsedLogEntry {
  return {
    id,
    timestamp,
    level,
    message,
    source,
    sortAt,
    searchText: `${message.toLowerCase()} ${source.toLowerCase()}`,
  };
}

function deriveApiLogs(providers: Provider[], jobs: Job[], runs: Run[]): ParsedLogEntry[] {
  const entries: ParsedLogEntry[] = [];
  let ordinal = 0;

  if (providers.length > 0 || jobs.length > 0 || runs.length > 0) {
    const now = Date.now();
    entries.push(
      buildEntry(
        `api-${ordinal++}`,
        formatLogTimestamp(new Date(now).toISOString()),
        "INFO",
        `Runtime snapshot received (${providers.length} providers, ${jobs.length} jobs, ${runs.length} runs)`,
        "api/runtime",
        now,
      ),
    );
  }

  providers.forEach((provider) => {
    entries.push(
      buildEntry(
        `api-${ordinal++}`,
        formatLogTimestamp(provider.updated_at),
        "INFO",
        `Provider ${provider.name} online (${provider.kind.replace(/_/g, " ")})`,
        "api/providers",
        timestampToMs(provider.updated_at),
      ),
    );
  });

  jobs.forEach((job) => {
    entries.push(
      buildEntry(
        `api-${ordinal++}`,
        formatLogTimestamp(job.updated_at),
        mapJobLogLevel(job.status),
        `Job ${job.id.slice(0, 8)} ${job.status}: ${job.dataset_label}`,
        "api/jobs",
        timestampToMs(job.updated_at),
      ),
    );
  });

  runs.forEach((run) => {
    const warningRate = run.metrics?.warning_rate;
    const warningRateText = typeof warningRate === "number" ? ` warning_rate=${warningRate.toFixed(3)}` : "";
    const runLevel = mapRunLogLevel(run.status);
    entries.push(
      buildEntry(
        `api-${ordinal++}`,
        formatLogTimestamp(run.updated_at),
        runLevel,
        `Run ${run.id.slice(0, 8)} ${run.status}: ${run.dataset_label}${warningRateText}`,
        "api/runs",
        timestampToMs(run.updated_at),
      ),
    );

    if (typeof warningRate === "number" && warningRate >= 0.2) {
      entries.push(
        buildEntry(
          `api-${ordinal++}`,
          formatLogTimestamp(run.updated_at),
          "WARN",
          `Run ${run.id.slice(0, 8)} warning-rate threshold breached (${warningRate.toFixed(3)})`,
          "api/runs/anomaly",
          timestampToMs(run.updated_at),
        ),
      );
    }
  });

  return entries.sort((a, b) => b.sortAt - a.sortAt).slice(0, 250);
}

function deriveMockLogs(): ParsedLogEntry[] {
  return gkpLogs
    .map((log, index) =>
      buildEntry(
        `mock-${index}`,
        log.timestamp,
        log.level,
        log.message,
        log.source,
        timestampToMs(log.timestamp),
      ),
    )
    .sort((a, b) => b.sortAt - a.sortAt);
}

function toFileTimestamp(): string {
  return new Date().toISOString().replace(/[-:.TZ]/g, "").slice(0, 14);
}

function downloadTextFile(filename: string, mime: string, content: string): void {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

function formatRatio(numerator: number, denominator: number): string {
  if (denominator <= 0) {
    return "0.0%";
  }
  return `${((numerator / denominator) * 100).toFixed(1)}%`;
}

function formatAgeFromNow(timestampMs: number): string {
  if (timestampMs <= 0) {
    return "unknown";
  }
  const deltaMs = Math.max(0, Date.now() - timestampMs);
  const deltaMinutes = Math.floor(deltaMs / 60_000);
  if (deltaMinutes < 1) {
    return "just now";
  }
  if (deltaMinutes < 60) {
    return `${deltaMinutes}m ago`;
  }
  const deltaHours = Math.floor(deltaMinutes / 60);
  if (deltaHours < 24) {
    return `${deltaHours}h ago`;
  }
  return `${Math.floor(deltaHours / 24)}d ago`;
}

export function LogsPage() {
  const [filterLevel, setFilterLevel] = useState<"all" | LogLevel>("all");
  const [sourceFilter, setSourceFilter] = useState<string>("all");
  const [timeWindow, setTimeWindow] = useState<TimeWindow>("24h");
  const [sortOrder, setSortOrder] = useState<SortOrder>("newest");
  const [scanProfile, setScanProfile] = useState<ScanProfileKey>("standard");
  const [scanScope, setScanScope] = useState<ScanScope>("filtered");
  const [searchTerm, setSearchTerm] = useState("");
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);
  const [maxFindings, setMaxFindings] = useState<number>(SCAN_PROFILES.standard.defaultMaxFindings);
  const [lastScanSampleSize, setLastScanSampleSize] = useState<number>(0);

  const { isApi, isMock, systemOff, systemArmed } = useDataMode();
  const apiEnabled = isApi && !systemOff && systemArmed;
  const deferredSearch = useDeferredValue(searchTerm.trim().toLowerCase());

  const providersQuery = useProviders({ enabled: apiEnabled });
  const jobsQuery = useJobs({ enabled: apiEnabled });
  const runsQuery = useRuns({ enabled: apiEnabled });
  const systemLogScan = useSystemLogScan();

  const viewerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setMaxFindings(SCAN_PROFILES[scanProfile].defaultMaxFindings);
  }, [scanProfile]);

  useEffect(() => {
    if (!apiEnabled || !autoRefresh) {
      return;
    }
    const timer = window.setInterval(() => {
      void providersQuery.refetch();
      void jobsQuery.refetch();
      void runsQuery.refetch();
    }, AUTO_REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [apiEnabled, autoRefresh, jobsQuery, providersQuery, runsQuery]);

  const apiLogs = systemOff ? [] : deriveApiLogs(providersQuery.data ?? [], jobsQuery.data ?? [], runsQuery.data ?? []);
  const mockLogs = deriveMockLogs();
  const allLogs: ParsedLogEntry[] = systemOff ? [] : isMock ? mockLogs : apiLogs;

  const sourceOptions = Array.from(new Set(allLogs.map((log) => log.source))).sort((a, b) => a.localeCompare(b));

  const activeWindowMs = TIME_WINDOW_MS[timeWindow];
  const nowMs = Date.now();
  const filteredLogs = allLogs.filter((log) => {
    const levelMatch = filterLevel === "all" || log.level === filterLevel;
    const sourceMatch = sourceFilter === "all" || log.source === sourceFilter;
    const searchMatch = deferredSearch.length === 0 || log.searchText.includes(deferredSearch);
    const timeMatch =
      activeWindowMs === null ||
      (log.sortAt > 0 && nowMs - log.sortAt <= activeWindowMs);
    return levelMatch && sourceMatch && searchMatch && timeMatch;
  });

  const scopedLogs =
    sortOrder === "newest"
      ? [...filteredLogs].sort((a, b) => b.sortAt - a.sortAt)
      : [...filteredLogs].sort((a, b) => a.sortAt - b.sortAt);

  const scanInputLogs = scanScope === "filtered" ? scopedLogs : allLogs;

  useEffect(() => {
    if (!autoScroll || !viewerRef.current) {
      return;
    }
    viewerRef.current.scrollTop = viewerRef.current.scrollHeight;
  }, [autoScroll, scopedLogs.length]);

  let errorCount = 0;
  let warnCount = 0;
  let infoCount = 0;
  let successCount = 0;
  const sourceCounts = new Map<string, number>();
  scopedLogs.forEach((log) => {
    if (log.level === "ERROR") {
      errorCount += 1;
    } else if (log.level === "WARN") {
      warnCount += 1;
    } else if (log.level === "INFO") {
      infoCount += 1;
    } else {
      successCount += 1;
    }
    sourceCounts.set(log.source, (sourceCounts.get(log.source) ?? 0) + 1);
  });

  const hottestSource = Array.from(sourceCounts.entries()).sort((a, b) => b[1] - a[1])[0];
  const lastEventAge = scopedLogs.length > 0 ? formatAgeFromNow(scopedLogs[0].sortAt) : "no events";

  const hasApiWarning = apiEnabled && (providersQuery.isError || jobsQuery.isError || runsQuery.isError);
  const isApiLoading = apiEnabled && (providersQuery.isLoading || jobsQuery.isLoading || runsQuery.isLoading);
  const noApiLogs = apiEnabled && !isApiLoading && !hasApiWarning && allLogs.length === 0;

  const scanReport = systemLogScan.data;
  const scanError =
    systemLogScan.error instanceof Error
      ? systemLogScan.error.message
      : "Failed to run research scan.";
  const topScanFindings = scanReport?.findings.slice(0, 20) ?? [];
  const activeProfile = SCAN_PROFILES[scanProfile];
  const verdictClass = scanReport ? mapScanVerdictToClassName(scanReport.summary.verdict) : "pass";

  const runResearchScan = () => {
    if (scanInputLogs.length === 0) {
      return;
    }
    const safeMaxFindings = Math.min(
      MAX_MAX_FINDINGS,
      Math.max(MIN_MAX_FINDINGS, Number.isFinite(maxFindings) ? Math.trunc(maxFindings) : activeProfile.defaultMaxFindings),
    );
    const payload = {
      logs: scanInputLogs.map((log) => ({
        timestamp: log.timestamp === "—" ? null : log.timestamp,
        level: log.level,
        message: log.message,
        source: log.source,
      })),
      custom_rules: activeProfile.customRules,
      suppressions: activeProfile.suppressions,
      max_findings: safeMaxFindings,
    };
    setLastScanSampleSize(scanInputLogs.length);
    systemLogScan.mutate(payload);
  };

  const refreshLiveData = async () => {
    if (!apiEnabled) {
      return;
    }
    await Promise.allSettled([providersQuery.refetch(), jobsQuery.refetch(), runsQuery.refetch()]);
  };

  const downloadCurrentLogs = () => {
    if (scopedLogs.length === 0) {
      return;
    }
    const lines = scopedLogs
      .slice(0, MAX_EXPORT_LINES)
      .map((log) =>
        JSON.stringify({
          timestamp: log.timestamp,
          level: log.level,
          source: log.source,
          message: log.message,
        }),
      )
      .join("\n");
    downloadTextFile(`system_logs_${toFileTimestamp()}.ndjson`, "application/x-ndjson;charset=utf-8", `${lines}\n`);
  };

  const downloadScanReport = () => {
    if (!scanReport) {
      return;
    }
    const payload = {
      scan_profile: scanProfile,
      scan_scope: scanScope,
      scanned_entries_requested: lastScanSampleSize,
      report: scanReport,
    };
    downloadTextFile(
      `system_logscan_report_${toFileTimestamp()}.json`,
      "application/json;charset=utf-8",
      `${JSON.stringify(payload, null, 2)}\n`,
    );
  };

  const clearFilters = () => {
    setFilterLevel("all");
    setSourceFilter("all");
    setTimeWindow("24h");
    setSearchTerm("");
  };

  return (
    <>
      <div className="header">
        <h1>System Logs</h1>
        <p>Research incident triage for decoder runtime, provider connectivity, and quality anomalies</p>
      </div>

      <div className="logs-toolbar">
        <div className="logs-filter-grid">
          <input
            type="text"
            className="search-box logs-search-box"
            placeholder="Search message/source (timeout, residual, provider, failover...)"
            value={searchTerm}
            onChange={(event) => setSearchTerm(event.target.value)}
          />
          <select
            className="logs-select"
            value={sourceFilter}
            onChange={(event) => setSourceFilter(event.target.value)}
          >
            <option value="all">All sources</option>
            {sourceOptions.map((source) => (
              <option key={source} value={source}>
                {source}
              </option>
            ))}
          </select>
          <select
            className="logs-select"
            value={timeWindow}
            onChange={(event) => setTimeWindow(event.target.value as TimeWindow)}
          >
            <option value="all">All time</option>
            <option value="15m">Last 15m</option>
            <option value="1h">Last 1h</option>
            <option value="24h">Last 24h</option>
          </select>
          <select
            className="logs-select"
            value={sortOrder}
            onChange={(event) => setSortOrder(event.target.value as SortOrder)}
          >
            <option value="newest">Newest first</option>
            <option value="oldest">Oldest first</option>
          </select>
          <select
            className="logs-select"
            value={scanProfile}
            onChange={(event) => setScanProfile(event.target.value as ScanProfileKey)}
          >
            {Object.entries(SCAN_PROFILES).map(([key, profile]) => (
              <option key={key} value={key}>
                Scan: {profile.label}
              </option>
            ))}
          </select>
          <select
            className="logs-select"
            value={scanScope}
            onChange={(event) => setScanScope(event.target.value as ScanScope)}
          >
            <option value="filtered">Scan filtered logs</option>
            <option value="all">Scan full stream</option>
          </select>
          <input
            type="number"
            className="logs-select logs-number-input"
            min={MIN_MAX_FINDINGS}
            max={MAX_MAX_FINDINGS}
            value={maxFindings}
            onChange={(event) => setMaxFindings(Number(event.target.value))}
            title="Max findings returned by scan"
          />
        </div>

        <div className="logs-action-row">
          {(["ERROR", "WARN", "INFO", "SUCCESS"] as const).map((level) => (
            <button
              key={level}
              className={`btn btn-secondary ${filterLevel === level ? "active" : ""}`}
              onClick={() => setFilterLevel(filterLevel === level ? "all" : level)}
            >
              ⊞ {level}
            </button>
          ))}
          <button className="btn btn-secondary" onClick={clearFilters}>
            Clear filters
          </button>
          <button
            className="btn btn-secondary"
            onClick={() => {
              void refreshLiveData();
            }}
            disabled={!apiEnabled || isApiLoading}
          >
            Refresh
          </button>
          <button
            className={`btn btn-secondary ${autoRefresh ? "active" : ""}`}
            onClick={() => setAutoRefresh((prev) => !prev)}
            disabled={!apiEnabled}
          >
            Auto-refresh {autoRefresh ? "On" : "Off"}
          </button>
          <button
            className={`btn btn-secondary ${autoScroll ? "active" : ""}`}
            onClick={() => setAutoScroll((prev) => !prev)}
          >
            Auto-scroll {autoScroll ? "On" : "Off"}
          </button>
          <button className="btn btn-secondary" onClick={downloadCurrentLogs} disabled={scopedLogs.length === 0}>
            Download NDJSON
          </button>
          <button
            className="btn btn-primary"
            onClick={runResearchScan}
            disabled={scanInputLogs.length === 0 || systemLogScan.isPending}
          >
            {systemLogScan.isPending ? "Scanning..." : "Research Scan"}
          </button>
        </div>

        <p className="scope-meta logs-scope-meta">
          {activeProfile.label} profile: {activeProfile.description} Scanning {scanInputLogs.length} entries from{" "}
          {scanScope === "filtered" ? "current filtered scope" : "full stream"}.
        </p>
      </div>

      <div className="logs-kpi-grid">
        <article className="logs-kpi-card">
          <span>Total in scope</span>
          <strong>{scopedLogs.length}</strong>
          <p>from {allLogs.length} collected events</p>
        </article>
        <article className="logs-kpi-card">
          <span>Error/Warn ratio</span>
          <strong>{formatRatio(errorCount + warnCount, Math.max(scopedLogs.length, 1))}</strong>
          <p>
            ERROR {errorCount} · WARN {warnCount}
          </p>
        </article>
        <article className="logs-kpi-card">
          <span>Signal split</span>
          <strong>
            INFO {infoCount} · OK {successCount}
          </strong>
          <p>non-critical operational signals</p>
        </article>
        <article className="logs-kpi-card">
          <span>Hottest source</span>
          <strong>{hottestSource ? hottestSource[0] : "n/a"}</strong>
          <p>{hottestSource ? `${hottestSource[1]} events` : "no source activity"}</p>
        </article>
        <article className="logs-kpi-card">
          <span>Freshness</span>
          <strong>{lastEventAge}</strong>
          <p>most recent event age</p>
        </article>
        <article className={`logs-kpi-card logs-kpi-scan ${scanReport ? `logs-kpi-${verdictClass}` : ""}`}>
          <span>Scan risk score</span>
          <strong>{scanReport ? `${scanReport.summary.risk_score}/100` : "—"}</strong>
          <p>{scanReport ? `verdict ${formatScanVerdict(scanReport.summary.verdict)}` : "run scan to evaluate risk"}</p>
        </article>
      </div>

      <div className="log-viewer" ref={viewerRef}>
        {scopedLogs.map((log) => (
          <div key={log.id} className="log-line">
            <span className="log-timestamp">{log.timestamp}</span>
            <span className={`log-level ${log.level.toLowerCase()}`}>{log.level}</span>
            <span className={`log-message ${deferredSearch && log.searchText.includes(deferredSearch) ? "highlight" : ""}`}>
              {log.message}
            </span>
            <span className="log-source">{log.source}</span>
          </div>
        ))}
        {scopedLogs.length === 0 ? (
          <div className="log-line">
            <span className="log-timestamp">—</span>
            <span className="log-level info">INFO</span>
            <span className="log-message">
              {isApiLoading ? "Loading logs from API..." : "No log entries for the current scope."}
            </span>
            <span className="log-source">ui/logs</span>
          </div>
        ) : null}
      </div>

      <div className="footer">
        <span>
          Showing {scopedLogs.length} of {allLogs.length} entries · {sourceOptions.length} unique sources · mode{" "}
          {isMock ? "GKP mock" : "API"}
        </span>
        <div className="log-controls">
          <button className="log-btn" onClick={downloadCurrentLogs} disabled={scopedLogs.length === 0}>
            Export View
          </button>
          <button className="log-btn" onClick={downloadScanReport} disabled={!scanReport}>
            Export Scan
          </button>
        </div>
      </div>

      {scanReport ? (
        <div className="empty-card section-offset logs-scan-report">
          <div className="logs-report-head">
            <strong>Research LogScan Report</strong>
            <span className={`logs-verdict logs-verdict-${verdictClass}`}>
              {formatScanVerdict(scanReport.summary.verdict)}
            </span>
          </div>
          <p>
            Scan ID: {scanReport.scan_id} · Generated: {formatLogTimestamp(scanReport.generated_at)} · Scanned:{" "}
            {scanReport.summary.scanned_entries} · Matched: {scanReport.summary.matched_entries} · Suppressed:{" "}
            {scanReport.summary.suppressed_matches}
          </p>
          <p>
            Severity profile: C={scanReport.summary.critical_count} H={scanReport.summary.high_count} M=
            {scanReport.summary.medium_count} L={scanReport.summary.low_count} I={scanReport.summary.info_count}
          </p>

          {scanReport.top_recommendations.length > 0 ? (
            <ul className="logs-recommendations">
              {scanReport.top_recommendations.slice(0, 4).map((rec) => (
                <li key={rec}>{rec}</li>
              ))}
            </ul>
          ) : null}

          <div className="log-viewer logs-findings-viewer">
            {topScanFindings.map((finding) => (
              <div key={`${finding.rule_id}-${finding.line_index}-${finding.title}`} className="log-line">
                <span className="log-timestamp">line {finding.line_index}</span>
                <span className={`log-level ${mapScanSeverityToLogLevel(finding.severity)}`}>
                  {finding.severity.toUpperCase()}
                </span>
                <span className="log-message">
                  [{finding.rule_origin}] {finding.title} ({Math.round(finding.confidence * 100)}%) — {finding.message}
                </span>
                <span className="log-source">{finding.rule_id}</span>
              </div>
            ))}
            {topScanFindings.length === 0 ? (
              <div className="log-line">
                <span className="log-timestamp">—</span>
                <span className="log-level success">PASS</span>
                <span className="log-message">No findings in returned scan report.</span>
                <span className="log-source">scan/report</span>
              </div>
            ) : null}
          </div>
        </div>
      ) : null}

      {systemLogScan.isError ? (
        <div className="empty-card section-offset">
          <strong>LogScan Error</strong>
          <p>{scanError}</p>
        </div>
      ) : null}

      {hasApiWarning ? (
        <div className="empty-card section-offset">
          <strong>API Warning</strong>
          <p>Some API resources could not be fetched. Log stream may be incomplete.</p>
        </div>
      ) : null}

      {noApiLogs ? (
        <div className="empty-card section-offset">
          <strong>No Live Logs Yet</strong>
          <p>The backend is reachable, but there are currently no provider/job/run events to render.</p>
        </div>
      ) : null}
    </>
  );
}
