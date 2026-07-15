import { useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { useIntegrationSessions, usePaper04Manifest, useProviders, useRunPaper04, useRuns } from "../../api/hooks";
import { ApiError } from "../../api/client";
import type { IntegrationSessionStatus, RunPaper04Response, RunStatus } from "../../api/types";
import { useDataMode } from "../../data/dataMode";
import { gkpProviders, gkpRuns } from "../../data/gkpFixtures";

function formatAgo(isoText: string | null | undefined): string {
  if (!isoText) {
    return "unknown";
  }
  const parsed = new Date(isoText).getTime();
  if (!Number.isFinite(parsed)) {
    return "unknown";
  }
  const minutes = Math.max(0, Math.floor((Date.now() - parsed) / 60_000));
  if (minutes < 1) {
    return "just now";
  }
  if (minutes < 60) {
    return `${minutes}m ago`;
  }
  const hours = Math.floor(minutes / 60);
  if (hours < 24) {
    return `${hours}h ago`;
  }
  return `${Math.floor(hours / 24)}d ago`;
}

function runStatusClass(status: RunStatus): string {
  if (status === "finished") {
    return "status-success";
  }
  if (status === "running" || status === "created") {
    return "status-running";
  }
  if (status === "cancelled") {
    return "status-warning";
  }
  return "status-failed";
}

function runStatusLabel(status: RunStatus): string {
  if (status === "finished") {
    return "Finished";
  }
  if (status === "running") {
    return "Running";
  }
  if (status === "created") {
    return "Created";
  }
  if (status === "cancelled") {
    return "Cancelled";
  }
  return "Failed";
}

function isTerminalRunStatus(status: RunStatus): boolean {
  return status === "finished" || status === "failed" || status === "cancelled";
}

function sessionStatusClass(status: IntegrationSessionStatus): string {
  if (status === "finished") {
    return "status-success";
  }
  if (status === "running" || status === "starting") {
    return "status-running";
  }
  if (status === "cancelled") {
    return "status-warning";
  }
  return "status-failed";
}

function sessionStatusLabel(status: IntegrationSessionStatus): string {
  if (status === "finished") {
    return "Finished";
  }
  if (status === "running") {
    return "Running";
  }
  if (status === "starting") {
    return "Starting";
  }
  if (status === "cancelled") {
    return "Cancelled";
  }
  return "Failed";
}

function paper04StatusClass(status: string): string {
  if (status === "succeeded") {
    return "status-success";
  }
  if (status === "running") {
    return "status-running";
  }
  if (status === "parity_mismatch") {
    return "status-warning";
  }
  if (status === "timeout") {
    return "status-warning";
  }
  return "status-failed";
}

function runWorkflowKey(raw: string | null | undefined): string {
  const value = (raw ?? "").trim();
  return value.length > 0 ? value : "unscoped";
}

function workflowLabel(workflowId: string): string {
  if (workflowId === "unscoped") {
    return "Unscoped";
  }
  return workflowId;
}

export function JobsPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { isApi, isMock, systemOff, systemArmed } = useDataMode();
  const apiEnabled = isApi && !systemOff && systemArmed;
  const providersQuery = useProviders({ enabled: apiEnabled });
  const runsQuery = useRuns({ enabled: apiEnabled, refetchInterval: 2_500 });
  const sessionsQuery = useIntegrationSessions({ enabled: apiEnabled, refetchInterval: 2_500 });
  const paper04ManifestQuery = usePaper04Manifest({ enabled: apiEnabled });
  const runPaper04Mutation = useRunPaper04();

  const providers = systemOff ? [] : isMock ? gkpProviders : providersQuery.data ?? [];
  const runs = systemOff ? [] : isMock ? gkpRuns : runsQuery.data ?? [];
  const sessions = systemOff ? [] : isMock ? [] : sessionsQuery.data ?? [];
  const providerById = useMemo(() => new Map(providers.map((provider) => [provider.id, provider])), [providers]);

  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | RunStatus>("all");
  const [providerFilter, setProviderFilter] = useState("all");
  const workflowFilter = (searchParams.get("workflow") ?? "all").trim() || "all";
  const [paper04StrictThreeStack, setPaper04StrictThreeStack] = useState(false);
  const [paper04EnableParamSweeps, setPaper04EnableParamSweeps] = useState(false);
  const [paper04TimeoutSeconds, setPaper04TimeoutSeconds] = useState("10800");
  const [paper04BaselineHash, setPaper04BaselineHash] = useState<string | null>(null);
  const [paper04BaselineCapturedAt, setPaper04BaselineCapturedAt] = useState<string | null>(null);
  const [paper04ActionStatus, setPaper04ActionStatus] = useState<"running" | "succeeded" | "failed" | "parity_mismatch">(
    "running",
  );
  const [paper04ActionMessage, setPaper04ActionMessage] = useState("Ready");
  const [paper04LastRun, setPaper04LastRun] = useState<RunPaper04Response | null>(null);
  const [analysisWorkflowId, setAnalysisWorkflowId] = useState<string | null>(null);

  const providerScopedRunsForWorkflow = useMemo(() => {
    return runs.filter((run) => {
      if (providerFilter !== "all" && run.provider_id !== providerFilter) {
        return false;
      }
      return true;
    });
  }, [providerFilter, runs]);

  const workflowOptions = useMemo(() => {
    const ids = new Set<string>(["paper_04"]);
    for (const run of providerScopedRunsForWorkflow) {
      ids.add(runWorkflowKey(run.workflow_id));
    }
    return Array.from(ids).sort((left, right) => {
      if (left === "paper_04") {
        return -1;
      }
      if (right === "paper_04") {
        return 1;
      }
      if (left === "unscoped") {
        return 1;
      }
      if (right === "unscoped") {
        return -1;
      }
      return left.localeCompare(right);
    });
  }, [providerScopedRunsForWorkflow]);

  const effectiveWorkflowFilter =
    workflowFilter !== "all" && !workflowOptions.includes(workflowFilter)
      ? "all"
      : workflowFilter;

  const setWorkflowFilter = (value: string) => {
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      if (value === "all") {
        next.delete("workflow");
      } else {
        next.set("workflow", value);
      }
      return next;
    });
  };

  const workflowSummaries = useMemo(() => {
    const runIdsByWorkflow = new Map<string, string[]>();
    for (const run of providerScopedRunsForWorkflow) {
      const key = runWorkflowKey(run.workflow_id);
      const existing = runIdsByWorkflow.get(key) ?? [];
      existing.push(run.id);
      runIdsByWorkflow.set(key, existing);
    }

    if (!runIdsByWorkflow.has("paper_04")) {
      runIdsByWorkflow.set("paper_04", []);
    }

    const sessionByRunId = new Map<string, IntegrationSessionStatus[]>();
    for (const session of sessions) {
      const existing = sessionByRunId.get(session.run_id) ?? [];
      existing.push(session.status);
      sessionByRunId.set(session.run_id, existing);
    }

    return Array.from(runIdsByWorkflow.entries())
      .map(([workflowId, runIds]) => {
        const workflowRuns = providerScopedRunsForWorkflow.filter((run) => runIds.includes(run.id));
        const statusCounts: Record<RunStatus, number> = {
          created: 0,
          running: 0,
          finished: 0,
          failed: 0,
          cancelled: 0,
        };
        for (const run of workflowRuns) {
          statusCounts[run.status] += 1;
        }
        const activeRuns = workflowRuns.filter((run) => run.status === "created" || run.status === "running").length;
        const completedRuns = workflowRuns.filter((run) => isTerminalRunStatus(run.status)).length;
        const completionPct =
          runIds.length === 0 ? 0 : Math.round((completedRuns / Math.max(1, runIds.length)) * 100);
        const decoderCoverage = new Set(workflowRuns.flatMap((run) => run.decoders)).size;
        const providerCoverage = new Set(workflowRuns.map((run) => run.provider_id)).size;
        const lastUpdatedAt =
          workflowRuns.length === 0
            ? null
            : workflowRuns
                .map((run) => run.updated_at)
                .sort((left, right) => new Date(right).getTime() - new Date(left).getTime())[0];
        const activeSessions = runIds.reduce((count, runId) => {
          const statuses = sessionByRunId.get(runId) ?? [];
          return count + statuses.filter((status) => status === "running" || status === "starting").length;
        }, 0);
        return {
          workflowId,
          runCount: runIds.length,
          activeRuns,
          completedRuns,
          completionPct,
          activeSessions,
          statusCounts,
          decoderCoverage,
          providerCoverage,
          lastUpdatedAt,
        };
      })
      .sort((left, right) => {
        if (left.workflowId === "paper_04") {
          return -1;
        }
        if (right.workflowId === "paper_04") {
          return 1;
        }
        if (left.runCount !== right.runCount) {
          return right.runCount - left.runCount;
        }
        return left.workflowId.localeCompare(right.workflowId);
      });
  }, [providerScopedRunsForWorkflow, sessions]);

  const selectedWorkflowSummary = useMemo(
    () => workflowSummaries.find((entry) => entry.workflowId === analysisWorkflowId) ?? null,
    [analysisWorkflowId, workflowSummaries],
  );

  const filteredRuns = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    return providerScopedRunsForWorkflow.filter((run) => {
      if (statusFilter !== "all" && run.status !== statusFilter) {
        return false;
      }
      const workflowKey = runWorkflowKey(run.workflow_id);
      if (effectiveWorkflowFilter !== "all" && workflowKey !== effectiveWorkflowFilter) {
        return false;
      }
      if (!query) {
        return true;
      }
      const providerName = providerById.get(run.provider_id)?.name ?? run.provider_id;
      return (
        run.id.toLowerCase().includes(query) ||
        run.dataset_label.toLowerCase().includes(query) ||
        providerName.toLowerCase().includes(query) ||
        workflowLabel(workflowKey).toLowerCase().includes(query) ||
        run.decoders.join(",").toLowerCase().includes(query)
      );
    });
  }, [effectiveWorkflowFilter, providerById, providerScopedRunsForWorkflow, searchQuery, statusFilter]);

  const workflowCoverageCount = useMemo(() => {
    const ids = new Set<string>();
    for (const run of providerScopedRunsForWorkflow) {
      ids.add(runWorkflowKey(run.workflow_id));
    }
    return ids.size;
  }, [providerScopedRunsForWorkflow]);

  const filteredSessions = useMemo(() => {
    const runIds = new Set(filteredRuns.map((run) => run.id));
    return sessions.filter((session) => runIds.has(session.run_id));
  }, [filteredRuns, sessions]);

  const latestUpdatedAt = useMemo(() => {
    const stamps = [
      ...filteredRuns.map((run) => run.updated_at),
      ...filteredSessions.map((session) => session.updated_at),
    ];
    if (stamps.length === 0) {
      return null;
    }
    return stamps.sort((a, b) => new Date(b).getTime() - new Date(a).getTime())[0];
  }, [filteredRuns, filteredSessions]);

  const handleCapturePaper04Baseline = async () => {
    if (!apiEnabled) {
      return;
    }
    setPaper04ActionStatus("running");
    setPaper04ActionMessage("Capturing CLI baseline manifest...");
    try {
      const response = await paper04ManifestQuery.refetch();
      const manifest = response.data;
      if (!manifest) {
        setPaper04ActionStatus("failed");
        setPaper04ActionMessage("Unable to read paper_04 manifest.");
        return;
      }
      setPaper04BaselineHash(manifest.manifest_hash);
      const now = new Date().toISOString();
      setPaper04BaselineCapturedAt(now);
      setPaper04ActionStatus("succeeded");
      setPaper04ActionMessage(`Baseline captured (${manifest.manifest_hash.slice(0, 12)}…).`);
    } catch (error) {
      const message = error instanceof ApiError ? error.message : "Failed to capture baseline manifest.";
      setPaper04ActionStatus("failed");
      setPaper04ActionMessage(message);
    }
  };

  const handleRunPaper04 = async () => {
    if (!apiEnabled) {
      return;
    }
    const parsedTimeout = Number.parseInt(paper04TimeoutSeconds.trim(), 10);
    if (!Number.isFinite(parsedTimeout) || parsedTimeout <= 0) {
      setPaper04ActionStatus("failed");
      setPaper04ActionMessage("Timeout must be a positive integer.");
      return;
    }

    setPaper04ActionStatus("running");
    setPaper04ActionMessage("Running paper_04 workflow through LiDMaS+...");
    try {
      const response = await runPaper04Mutation.mutateAsync({
        strict_three_stack: paper04StrictThreeStack,
        enable_param_sweeps: paper04EnableParamSweeps,
        timeout_seconds: parsedTimeout,
        compare_with_manifest_hash: paper04BaselineHash ?? undefined,
      });
      setPaper04LastRun(response);
      if (response.status === "succeeded") {
        setPaper04ActionStatus("succeeded");
        setPaper04ActionMessage(
          `paper_04 completed (manifest ${response.manifest.manifest_hash.slice(0, 12)}…).`,
        );
      } else if (response.status === "parity_mismatch") {
        setPaper04ActionStatus("parity_mismatch");
        setPaper04ActionMessage("paper_04 completed, but manifest parity differs from CLI baseline.");
      } else {
        setPaper04ActionStatus("failed");
        setPaper04ActionMessage(`paper_04 ended with status '${response.status}'.`);
      }
    } catch (error) {
      const message = error instanceof ApiError ? error.message : "Failed to run paper_04 workflow.";
      setPaper04ActionStatus("failed");
      setPaper04ActionMessage(message);
    }
  };

  return (
    <>
      <div className="header">
        <h1>Runs</h1>
        <p>Replay history, execution sessions, and decoder run orchestration.</p>
      </div>

      <div className="trust-strip">
        <div className="trust-item">
          <span>Data Source</span>
          <strong>{systemOff ? "Off" : !systemArmed ? "Standby" : isMock ? "GKP Mock" : "Live API"}</strong>
        </div>
        <div className="trust-item">
          <span>Runs in Scope</span>
          <strong>{filteredRuns.length}</strong>
        </div>
        <div className="trust-item">
          <span>Active Sessions</span>
          <strong>{filteredSessions.filter((session) => session.status === "running" || session.status === "starting").length}</strong>
        </div>
        <div className="trust-item">
          <span>Decoder Coverage</span>
          <strong>{new Set(filteredRuns.flatMap((run) => run.decoders)).size} decoders</strong>
        </div>
        <div className="trust-item">
          <span>Workflow Coverage</span>
          <strong>{workflowCoverageCount} workflows</strong>
        </div>
        <div className="trust-item">
          <span>Last Refresh</span>
          <strong>{formatAgo(latestUpdatedAt)}</strong>
        </div>
      </div>

      <div className="table-container runs-workflow-panel">
        <div className="table-wrapper">
          <div className="section-title">Workflow Stack</div>
          <div className="panel-subtitle">
            Workflow protocols are orchestration layers. Providers remain hardware/simulator execution sources.
          </div>
          <div className="runs-workflow-stack-grid">
            {workflowSummaries.map((entry) => {
              const isActive = effectiveWorkflowFilter === entry.workflowId;
              return (
                <div key={entry.workflowId} className={`runs-workflow-stack-item ${isActive ? "is-active" : ""}`}>
                  <div className="runs-workflow-stack-head">
                    <span className={`runs-workflow-pill ${entry.workflowId === "paper_04" ? "is-paper" : ""}`}>
                      {workflowLabel(entry.workflowId)}
                    </span>
                    <div className="runs-workflow-stack-actions">
                      <button
                        type="button"
                        className={`btn btn-small runs-workflow-filter-btn ${isActive ? "is-active" : ""}`}
                        onClick={() => setWorkflowFilter(isActive ? "all" : entry.workflowId)}
                      >
                        {isActive ? "Clear Filter" : "Filter"}
                      </button>
                      <button
                        type="button"
                        className={`btn btn-small runs-workflow-analysis-btn ${
                          analysisWorkflowId === entry.workflowId ? "is-active" : ""
                        }`}
                        onClick={() => setAnalysisWorkflowId(entry.workflowId)}
                      >
                        Analysis
                      </button>
                    </div>
                  </div>
                  <div className="runs-workflow-progress">
                    <div className="runs-workflow-progress-head">
                      <span>Completion</span>
                      <strong>{entry.completionPct}%</strong>
                    </div>
                    <div
                      className="runs-workflow-progress-track"
                      role="progressbar"
                      aria-valuenow={entry.completionPct}
                      aria-valuemin={0}
                      aria-valuemax={100}
                    >
                      <span className="runs-workflow-progress-fill" style={{ width: `${entry.completionPct}%` }} />
                    </div>
                    <div className="runs-workflow-progress-caption">
                      {entry.completedRuns} of {entry.runCount} runs completed
                    </div>
                  </div>
                  <div className="runs-workflow-stack-metrics">
                    <span>Runs: <strong>{entry.runCount}</strong></span>
                    <span>Active Runs: <strong>{entry.activeRuns}</strong></span>
                    <span>Active Sessions: <strong>{entry.activeSessions}</strong></span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <div className="table-container runs-parity-panel">
        <div className="table-wrapper">
          <div className="section-title">paper_04 Parity</div>
          <div className="panel-subtitle">
            Run the same paper workflow used by CLI and compare artifact manifest hashes for IDE/CLI parity.
          </div>
          <div className="scope-meta">
            Canonical CLI command: <code>./examples/paper_runs/paper_04/run_all.sh</code>
          </div>
          <div className="paper04-runner-controls">
            <label className="paper04-runner-check">
              <input
                type="checkbox"
                checked={paper04StrictThreeStack}
                onChange={(event) => setPaper04StrictThreeStack(event.target.checked)}
                disabled={!apiEnabled || runPaper04Mutation.isPending}
              />
              Strict PennyLane/Qiskit/Cirq required
            </label>
            <label className="paper04-runner-check">
              <input
                type="checkbox"
                checked={paper04EnableParamSweeps}
                onChange={(event) => setPaper04EnableParamSweeps(event.target.checked)}
                disabled={!apiEnabled || runPaper04Mutation.isPending}
              />
              Enable parameter sweeps
            </label>
            <label className="paper04-runner-timeout">
              Timeout (seconds)
              <input
                type="text"
                className="form-input"
                value={paper04TimeoutSeconds}
                onChange={(event) => setPaper04TimeoutSeconds(event.target.value)}
                disabled={!apiEnabled || runPaper04Mutation.isPending}
              />
            </label>
          </div>
          <div className="paper04-runner-actions">
            <button
              className="btn btn-secondary"
              onClick={handleCapturePaper04Baseline}
              disabled={!apiEnabled || runPaper04Mutation.isPending || paper04ManifestQuery.isFetching}
            >
              Capture CLI Baseline
            </button>
            <button
              className="btn btn-primary"
              onClick={handleRunPaper04}
              disabled={!apiEnabled || runPaper04Mutation.isPending}
            >
              Run paper_04 In LiDMaS+
            </button>
            <span className={`status-badge ${paper04StatusClass(paper04ActionStatus)}`}>● {paper04ActionMessage}</span>
          </div>
          <div className="scope-meta">
            Baseline: {paper04BaselineHash ? `${paper04BaselineHash.slice(0, 16)}…` : "not captured"} · Captured:{" "}
            {paper04BaselineCapturedAt ? formatAgo(paper04BaselineCapturedAt) : "n/a"} · Current manifest:{" "}
            {paper04ManifestQuery.data?.manifest_hash ? `${paper04ManifestQuery.data.manifest_hash.slice(0, 16)}…` : "n/a"}
          </div>
          {paper04LastRun ? (
            <>
              <div className="scope-meta">
                Last run: status <code>{paper04LastRun.status}</code> · exit{" "}
                <code>{paper04LastRun.exit_code ?? "none"}</code> · duration{" "}
                <code>{(paper04LastRun.duration_ms / 1000).toFixed(1)}s</code> · artifacts{" "}
                <code>{paper04LastRun.manifest.artifact_count}</code>
              </div>
              {paper04LastRun.parity ? (
                <div className="scope-meta">
                  Parity:{" "}
                  <strong>{paper04LastRun.parity.match_exact ? "MATCH" : "MISMATCH"}</strong> · expected{" "}
                  <code>{paper04LastRun.parity.expected_manifest_hash.slice(0, 16)}…</code> · actual{" "}
                  <code>{paper04LastRun.parity.actual_manifest_hash.slice(0, 16)}…</code>
                </div>
              ) : null}
              <div className="paper04-runner-log-grid">
                <div>
                  <div className="scope-meta">stdout tail</div>
                  <pre className="paper04-runner-log-tail">
                    {paper04LastRun.stdout_tail.length > 0 ? paper04LastRun.stdout_tail.join("\n") : "(empty)"}
                  </pre>
                </div>
                <div>
                  <div className="scope-meta">stderr tail</div>
                  <pre className="paper04-runner-log-tail">
                    {paper04LastRun.stderr_tail.length > 0 ? paper04LastRun.stderr_tail.join("\n") : "(empty)"}
                  </pre>
                </div>
              </div>
            </>
          ) : null}
        </div>
      </div>

      <div className="dashboard-filterbar">
        <div className="filter-group">
          <label>Search</label>
          <input
            type="text"
            className="search-box research-search"
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
            placeholder="Run id, dataset, provider, workflow, decoder..."
          />
        </div>
        <div className="filter-group">
          <label>Status</label>
          <select
            className="select-field research-select"
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value as "all" | RunStatus)}
          >
            <option value="all">All</option>
            <option value="created">Created</option>
            <option value="running">Running</option>
            <option value="finished">Finished</option>
            <option value="failed">Failed</option>
            <option value="cancelled">Cancelled</option>
          </select>
        </div>
        <div className="filter-group">
          <label>Provider</label>
          <select
            className="select-field research-select"
            value={providerFilter}
            onChange={(event) => setProviderFilter(event.target.value)}
          >
            <option value="all">All Providers</option>
            {providers.map((provider) => (
              <option key={provider.id} value={provider.id}>
                {provider.name}
              </option>
            ))}
          </select>
        </div>
        <div className="filter-group">
          <label>Workflow</label>
          <select
            className="select-field research-select"
            value={effectiveWorkflowFilter}
            onChange={(event) => setWorkflowFilter(event.target.value)}
          >
            <option value="all">All Workflows</option>
            {workflowOptions.map((workflowId) => (
              <option key={workflowId} value={workflowId}>
                {workflowLabel(workflowId)}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="section-title">Run History</div>
      <div className="panel-subtitle">Primary replay and execution list with direct links to decoder telemetry.</div>
      {filteredRuns.length === 0 ? (
        <div className="empty-card">
          <strong>No Runs In Scope</strong>
          <p>Adjust filters or execute a replay session.</p>
        </div>
      ) : (
        <div className="table-container">
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Run</th>
                  <th>Dataset</th>
                  <th>Provider</th>
                  <th>Workflow</th>
                  <th>Decoders</th>
                  <th>Status</th>
                  <th>Updated</th>
                  <th>Telemetry</th>
                </tr>
              </thead>
              <tbody>
                {filteredRuns.map((run) => (
                  <tr key={run.id}>
                    <td>{run.id.slice(0, 8).toUpperCase()}</td>
                    <td>{run.dataset_label}</td>
                    <td>{providerById.get(run.provider_id)?.name ?? run.provider_id}</td>
                    <td>
                      <span
                        className={`runs-workflow-pill ${
                          runWorkflowKey(run.workflow_id) === "paper_04" ? "is-paper" : ""
                        }`}
                      >
                        {workflowLabel(runWorkflowKey(run.workflow_id))}
                      </span>
                    </td>
                    <td>
                      <div className="runs-decoder-list">
                        {run.decoders.map((decoder) => (
                          <span key={`${run.id}-${decoder}`} className="runs-decoder-pill">
                            {decoder}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td>
                      <span className={`status-badge ${runStatusClass(run.status)}`}>● {runStatusLabel(run.status)}</span>
                    </td>
                    <td>{formatAgo(run.updated_at)}</td>
                    <td>
                      <button
                        className="provider-link-btn"
                        onClick={() => navigate(`/decoder/telemetry?runA=${encodeURIComponent(run.id)}&compare=0`)}
                      >
                        Open
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="section-title section-offset">Adapter Sessions</div>
      <div className="panel-subtitle">Operational session history for adapters and hardware replay workers.</div>
      {filteredSessions.length === 0 ? (
        <div className="scientific-muted-note">No adapter sessions in the current run scope.</div>
      ) : (
        <div className="table-container">
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Session</th>
                  <th>Run</th>
                  <th>Provider</th>
                  <th>Adapter</th>
                  <th>Status</th>
                  <th>Updated</th>
                </tr>
              </thead>
              <tbody>
                {filteredSessions.map((session) => (
                  <tr key={session.id}>
                    <td>{session.id.slice(0, 8).toUpperCase()}</td>
                    <td>{session.run_id.slice(0, 8).toUpperCase()}</td>
                    <td>{session.provider.toUpperCase()}</td>
                    <td>{session.adapter_id}</td>
                    <td>
                      <span className={`status-badge ${sessionStatusClass(session.status)}`}>
                        ● {sessionStatusLabel(session.status)}
                      </span>
                    </td>
                    <td>{formatAgo(session.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {selectedWorkflowSummary ? (
        <div className="modal-overlay" onClick={() => setAnalysisWorkflowId(null)}>
          <div className="modal runs-analysis-modal" onClick={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <div>
                <div className="modal-title">{workflowLabel(selectedWorkflowSummary.workflowId)} Analysis</div>
                <div className="modal-subtitle">Run completion and execution breakdown for the selected workflow.</div>
              </div>
              <button type="button" className="modal-close" onClick={() => setAnalysisWorkflowId(null)}>
                ×
              </button>
            </div>
            <div className="modal-body">
              <div className="runs-analysis-progress-head">
                <span>Completion</span>
                <strong>{selectedWorkflowSummary.completionPct}%</strong>
              </div>
              <div
                className="runs-analysis-progress-track"
                role="progressbar"
                aria-valuenow={selectedWorkflowSummary.completionPct}
                aria-valuemin={0}
                aria-valuemax={100}
              >
                <span
                  className="runs-analysis-progress-fill"
                  style={{ width: `${selectedWorkflowSummary.completionPct}%` }}
                />
              </div>
              <div className="runs-analysis-progress-caption">
                {selectedWorkflowSummary.completedRuns} completed / {selectedWorkflowSummary.runCount} total
              </div>

              <div className="runs-analysis-figures-grid">
                <div className="runs-analysis-figure-card">
                  <span>Active Runs</span>
                  <strong>{selectedWorkflowSummary.activeRuns}</strong>
                </div>
                <div className="runs-analysis-figure-card">
                  <span>Active Sessions</span>
                  <strong>{selectedWorkflowSummary.activeSessions}</strong>
                </div>
                <div className="runs-analysis-figure-card">
                  <span>Provider Coverage</span>
                  <strong>{selectedWorkflowSummary.providerCoverage}</strong>
                </div>
                <div className="runs-analysis-figure-card">
                  <span>Decoder Coverage</span>
                  <strong>{selectedWorkflowSummary.decoderCoverage}</strong>
                </div>
                <div className="runs-analysis-figure-card">
                  <span>Last Updated</span>
                  <strong>{formatAgo(selectedWorkflowSummary.lastUpdatedAt)}</strong>
                </div>
                <div className="runs-analysis-figure-card">
                  <span>Total Runs</span>
                  <strong>{selectedWorkflowSummary.runCount}</strong>
                </div>
              </div>

              <div className="runs-analysis-status-list">
                {(["created", "running", "finished", "failed", "cancelled"] as RunStatus[]).map((status) => {
                  const count = selectedWorkflowSummary.statusCounts[status];
                  const pct =
                    selectedWorkflowSummary.runCount === 0
                      ? 0
                      : Math.round((count / selectedWorkflowSummary.runCount) * 100);
                  return (
                    <div key={status} className="runs-analysis-status-row">
                      <div className="runs-analysis-status-head">
                        <span>{runStatusLabel(status)}</span>
                        <strong>
                          {count} ({pct}%)
                        </strong>
                      </div>
                      <div className="runs-analysis-status-track">
                        <span
                          className={`runs-analysis-status-fill runs-analysis-status-fill-${status}`}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
            <div className="modal-footer">
              <button type="button" className="btn btn-secondary" onClick={() => setAnalysisWorkflowId(null)}>
                Close
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
