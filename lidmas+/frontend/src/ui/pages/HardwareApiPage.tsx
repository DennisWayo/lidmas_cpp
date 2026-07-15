import { useEffect, useMemo, useState } from "react";

import { API_BASE_URL, ApiError } from "../../api/client";
import {
  useCompleteHardwareSession,
  useCreateHardwareSession,
  useHardwareSchema,
  useHardwareSessions,
  useIngestHardwareFrames,
  useProviders,
  useRuns,
} from "../../api/hooks";
import type {
  HardwareSession,
  HardwareSessionStatus,
  HardwareSourceMode,
  IngestHardwareFramesRequest,
} from "../../api/types";
import { useDataMode } from "../../data/dataMode";

type ActionTone = "neutral" | "good" | "warn" | "bad";

const DEFAULT_FRAME_REQUEST: IngestHardwareFramesRequest = {
  frames: [
    {
      frame_index: 0,
      timestamp: "2026-04-21T10:20:30Z",
      source: "ibm_live",
      backend_name: "ibm_kingston",
      warning_rate: 0.0193,
      noise_sample: {
        index: 0,
        physical_error_rate: 0.0152,
        displacement_sigma: 0.206,
        photon_loss_rate: 0.0048,
      },
      syndrome_samples: [
        { round: 0, stabilizer: "S01", value: 1, is_triggered: true },
        { round: 0, stabilizer: "S02", value: 0, is_triggered: false },
      ],
      decoder_interventions: [
        { decoder: "mwpm", round: 0, flips: 3, residual_weight: 1 },
        { decoder: "uf", round: 0, flips: 2, residual_weight: 1 },
        { decoder: "bp", round: 0, flips: 2, residual_weight: 2 },
      ],
    },
  ],
};

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
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function statusClass(status: HardwareSessionStatus): string {
  if (status === "active") {
    return "status-running";
  }
  if (status === "completed") {
    return "status-success";
  }
  if (status === "cancelled") {
    return "status-warning";
  }
  return "status-failed";
}

function statusLabel(status: HardwareSessionStatus): string {
  if (status === "active") {
    return "Active";
  }
  if (status === "completed") {
    return "Completed";
  }
  if (status === "cancelled") {
    return "Cancelled";
  }
  return "Failed";
}

function toneClass(tone: ActionTone): string {
  if (tone === "good") {
    return "status-success";
  }
  if (tone === "warn") {
    return "status-warning";
  }
  if (tone === "bad") {
    return "status-failed";
  }
  return "status-running";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function parseFramePayload(
  raw: string,
): { payload: IngestHardwareFramesRequest | null; error: string | null } {
  try {
    const parsed = JSON.parse(raw) as unknown;
    if (!isRecord(parsed)) {
      return { payload: null, error: "Payload must be a JSON object." };
    }
    const frames = parsed.frames;
    if (!Array.isArray(frames) || frames.length === 0) {
      return { payload: null, error: "Payload must include non-empty frames array." };
    }
    for (let index = 0; index < frames.length; index += 1) {
      const frame = frames[index];
      if (!isRecord(frame)) {
        return { payload: null, error: `frames[${index}] must be an object.` };
      }
      if (typeof frame.frame_index !== "number") {
        return { payload: null, error: `frames[${index}].frame_index must be numeric.` };
      }
      if (!isRecord(frame.noise_sample)) {
        return { payload: null, error: `frames[${index}].noise_sample must be an object.` };
      }
      if (!Array.isArray(frame.syndrome_samples)) {
        return { payload: null, error: `frames[${index}].syndrome_samples must be an array.` };
      }
      if (!Array.isArray(frame.decoder_interventions)) {
        return { payload: null, error: `frames[${index}].decoder_interventions must be an array.` };
      }
    }
    return { payload: parsed as unknown as IngestHardwareFramesRequest, error: null };
  } catch (error) {
    const message = error instanceof Error ? error.message : "Invalid JSON payload.";
    return { payload: null, error: message };
  }
}

function buildCurlExamples(
  session: HardwareSession | null,
  framePayloadText: string,
  createSessionPayload: Record<string, unknown>,
): { createCurl: string; ingestCurl: string; completeCurl: string } {
  const baseUrl = API_BASE_URL.replace(/\/+$/, "");
  const createJson = JSON.stringify(createSessionPayload, null, 2);
  const createCurl = [
    `curl -X POST "${baseUrl}/hardware/sessions" \\`,
    `  -H "Authorization: Bearer <token>" \\`,
    `  -H "Content-Type: application/json" \\`,
    `  -d '${createJson}'`,
  ].join("\n");

  const sessionId = session?.id ?? "<session_id>";
  const ingestCurl = [
    `curl -X POST "${baseUrl}/hardware/sessions/${sessionId}/frames" \\`,
    `  -H "Authorization: Bearer <token>" \\`,
    `  -H "Content-Type: application/json" \\`,
    `  -d '${framePayloadText}'`,
  ].join("\n");

  const completeCurl = [
    `curl -X POST "${baseUrl}/hardware/sessions/${sessionId}/complete" \\`,
    `  -H "Authorization: Bearer <token>" \\`,
    `  -H "Content-Type: application/json" \\`,
    `  -d '{}'`,
  ].join("\n");

  return { createCurl, ingestCurl, completeCurl };
}

export function HardwareApiPage() {
  const { isApi, isMock, systemOff, systemArmed } = useDataMode();
  const apiEnabled = isApi && !systemOff && systemArmed;
  const providersQuery = useProviders({ enabled: apiEnabled });
  const runsQuery = useRuns({ enabled: apiEnabled });
  const schemaQuery = useHardwareSchema({ enabled: apiEnabled });
  const sessionsQuery = useHardwareSessions({ enabled: apiEnabled, refetchInterval: 2500 });
  const createSessionMutation = useCreateHardwareSession();
  const ingestFramesMutation = useIngestHardwareFrames();
  const completeSessionMutation = useCompleteHardwareSession();

  const providers = systemOff ? [] : providersQuery.data ?? [];
  const runs = systemOff ? [] : runsQuery.data ?? [];
  const sessions = systemOff ? [] : sessionsQuery.data ?? [];

  const providerLookup = useMemo(
    () => new Map(providers.map((provider) => [provider.id, provider])),
    [providers],
  );
  const runLookup = useMemo(() => new Map(runs.map((run) => [run.id, run])), [runs]);

  const [providerId, setProviderId] = useState("");
  const [datasetLabel, setDatasetLabel] = useState("external_noise_stream");
  const [decodersText, setDecodersText] = useState("mwpm,uf,bp");
  const [sourceName, setSourceName] = useState("lab-qpu-rack-3");
  const [sourceMode, setSourceMode] = useState<HardwareSourceMode>("live");
  const [schemaVersion, setSchemaVersion] = useState("lidmas.hardware.v1");
  const [activeSessionId, setActiveSessionId] = useState("");
  const [framePayloadText, setFramePayloadText] = useState(`${JSON.stringify(DEFAULT_FRAME_REQUEST, null, 2)}\n`);
  const [framePayloadDirty, setFramePayloadDirty] = useState(false);
  const [actionMessage, setActionMessage] = useState("Ready.");
  const [actionTone, setActionTone] = useState<ActionTone>("neutral");

  useEffect(() => {
    if (providerId && providers.some((provider) => provider.id === providerId)) {
      return;
    }
    const firstProvider = providers[0];
    if (firstProvider) {
      setProviderId(firstProvider.id);
    }
  }, [providerId, providers]);

  useEffect(() => {
    if (schemaQuery.data?.schema_version) {
      setSchemaVersion(schemaQuery.data.schema_version);
    }
  }, [schemaQuery.data?.schema_version]);

  useEffect(() => {
    if (framePayloadDirty) {
      return;
    }
    const schemaPayload = schemaQuery.data?.frame_request_example;
    if (!schemaPayload) {
      return;
    }
    setFramePayloadText(`${JSON.stringify(schemaPayload, null, 2)}\n`);
  }, [framePayloadDirty, schemaQuery.data?.frame_request_example]);

  useEffect(() => {
    if (!sessions.length) {
      setActiveSessionId("");
      return;
    }
    if (activeSessionId && sessions.some((session) => session.id === activeSessionId)) {
      return;
    }
    const active = sessions.find((session) => session.status === "active");
    setActiveSessionId(active?.id ?? sessions[sessions.length - 1]?.id ?? "");
  }, [activeSessionId, sessions]);

  const selectedSession = useMemo(
    () => sessions.find((session) => session.id === activeSessionId) ?? null,
    [activeSessionId, sessions],
  );

  const payloadValidation = useMemo(() => parseFramePayload(framePayloadText), [framePayloadText]);

  const createSessionPayload = useMemo(
    () => ({
      provider_id: providerId || "<provider_id>",
      dataset_label: datasetLabel.trim() || "external_noise_stream",
      decoders: decodersText
        .split(",")
        .map((decoder) => decoder.trim())
        .filter((decoder) => decoder.length > 0),
      source_name: sourceName.trim() || "lab-qpu-rack-3",
      source_mode: sourceMode,
      schema_version: schemaVersion.trim() || "lidmas.hardware.v1",
    }),
    [datasetLabel, decodersText, providerId, schemaVersion, sourceMode, sourceName],
  );

  const curlExamples = useMemo(
    () => buildCurlExamples(selectedSession, framePayloadText, createSessionPayload),
    [createSessionPayload, framePayloadText, selectedSession],
  );

  const latestUpdatedAt =
    selectedSession?.updated_at ??
    sessions
      .slice()
      .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())[0]?.updated_at ??
    null;

  const loading = apiEnabled && (providersQuery.isLoading || sessionsQuery.isLoading || schemaQuery.isLoading);
  const error = apiEnabled && (providersQuery.isError || sessionsQuery.isError || schemaQuery.isError);

  const onCreateSession = async () => {
    if (!apiEnabled) {
      setActionMessage("System is off. Turn it on before creating hardware sessions.");
      setActionTone("warn");
      return;
    }
    if (!providerId) {
      setActionMessage("Select a provider before creating a hardware session.");
      setActionTone("warn");
      return;
    }
    const decoders = decodersText
      .split(",")
      .map((decoder) => decoder.trim())
      .filter((decoder) => decoder.length > 0);
    if (decoders.length === 0) {
      setActionMessage("Provide at least one decoder.");
      setActionTone("warn");
      return;
    }
    try {
      const response = await createSessionMutation.mutateAsync({
        provider_id: providerId,
        dataset_label: datasetLabel.trim(),
        decoders,
        source_name: sourceName.trim(),
        source_mode: sourceMode,
        schema_version: schemaVersion.trim(),
      });
      setActiveSessionId(response.session.id);
      setActionMessage(
        `Session ${response.session.id.slice(0, 8)} created with run ${response.run.id.slice(0, 8)}.`,
      );
      setActionTone("good");
    } catch (error) {
      const message = error instanceof ApiError ? error.message : "Failed to create hardware session.";
      setActionMessage(message);
      setActionTone("bad");
    }
  };

  const onIngestFrames = async () => {
    if (!apiEnabled) {
      setActionMessage("System is off. Turn it on before ingesting frames.");
      setActionTone("warn");
      return;
    }
    if (!selectedSession) {
      setActionMessage("Select or create a hardware session first.");
      setActionTone("warn");
      return;
    }
    if (!payloadValidation.payload) {
      setActionMessage(payloadValidation.error ?? "Frame payload is invalid.");
      setActionTone("warn");
      return;
    }
    try {
      const response = await ingestFramesMutation.mutateAsync({
        sessionId: selectedSession.id,
        payload: payloadValidation.payload,
      });
      setActionMessage(
        `Ingested ${response.ingested_frames} frame(s). Session total frames: ${response.session.frame_count}.`,
      );
      setActionTone("good");
    } catch (error) {
      const message = error instanceof ApiError ? error.message : "Failed to ingest frames.";
      setActionMessage(message);
      setActionTone("bad");
    }
  };

  const onCompleteSession = async () => {
    if (!apiEnabled) {
      setActionMessage("System is off. Turn it on before completing sessions.");
      setActionTone("warn");
      return;
    }
    if (!selectedSession) {
      setActionMessage("Select or create a hardware session first.");
      setActionTone("warn");
      return;
    }
    try {
      const response = await completeSessionMutation.mutateAsync(selectedSession.id);
      setActionMessage(
        `Session ${response.session.id.slice(0, 8)} completed. Run ${response.run.id.slice(0, 8)} is ${response.run.status}.`,
      );
      setActionTone("good");
    } catch (error) {
      const message = error instanceof ApiError ? error.message : "Failed to complete session.";
      setActionMessage(message);
      setActionTone("bad");
    }
  };

  return (
    <>
      <div className="header">
        <h1>Hardware API</h1>
        <p>Developer surface for ingesting hardware-derived telemetry into LiDMaS+.</p>
      </div>

      <div className="trust-strip">
        <div className="trust-item">
          <span>Data Source</span>
          <strong>{systemOff ? "Off" : !systemArmed ? "Standby" : isMock ? "GKP Mock" : "Live API"}</strong>
        </div>
        <div className="trust-item">
          <span>Schema Version</span>
          <strong>{schemaVersion || "n/a"}</strong>
        </div>
        <div className="trust-item">
          <span>Sessions</span>
          <strong>{sessions.length}</strong>
        </div>
        <div className="trust-item">
          <span>Selected Session</span>
          <strong>{selectedSession ? selectedSession.id.slice(0, 8) : "None"}</strong>
        </div>
        <div className="trust-item">
          <span>Last Refresh</span>
          <strong>{formatAgo(latestUpdatedAt)}</strong>
        </div>
      </div>

      <div className="scope-meta">
        Endpoints: <code>POST /api/v1/hardware/sessions</code>, <code>POST /api/v1/hardware/sessions/{"{id}"}/frames</code>,{" "}
        <code>POST /api/v1/hardware/sessions/{"{id}"}/complete</code>.
      </div>

      <div className="table-container">
        <div className="table-wrapper">
          <div className="section-title">Create Hardware Session</div>
          <div className="panel-subtitle">
            Start a run-backed ingestion session, then stream normalized frames into the session.
          </div>
          <div className="hardware-api-form">
            <div className="form-group">
              <label className="form-label">Provider</label>
              <select
                className="form-select"
                value={providerId}
                onChange={(event) => setProviderId(event.target.value)}
                disabled={!apiEnabled || providers.length === 0}
              >
                {providers.length === 0 ? <option value="">No provider available</option> : null}
                {providers.map((provider) => (
                  <option key={provider.id} value={provider.id}>
                    {provider.name} ({provider.kind})
                  </option>
                ))}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">Dataset Label</label>
              <input
                className="form-input"
                value={datasetLabel}
                onChange={(event) => setDatasetLabel(event.target.value)}
                placeholder="external_noise_stream"
              />
            </div>
            <div className="form-group">
              <label className="form-label">Source Name</label>
              <input
                className="form-input"
                value={sourceName}
                onChange={(event) => setSourceName(event.target.value)}
                placeholder="lab-qpu-rack-3"
              />
            </div>
            <div className="form-group">
              <label className="form-label">Source Mode</label>
              <select
                className="form-select"
                value={sourceMode}
                onChange={(event) => setSourceMode(event.target.value as HardwareSourceMode)}
              >
                <option value="live">Live</option>
                <option value="replay">Replay</option>
              </select>
            </div>
            <div className="form-group hardware-api-full-width">
              <label className="form-label">Decoders (comma-separated)</label>
              <input
                className="form-input"
                value={decodersText}
                onChange={(event) => setDecodersText(event.target.value)}
                placeholder="mwpm,uf,bp"
              />
            </div>
            <div className="form-group hardware-api-full-width">
              <label className="form-label">Schema Version</label>
              <input
                className="form-input"
                value={schemaVersion}
                onChange={(event) => setSchemaVersion(event.target.value)}
                placeholder="lidmas.hardware.v1"
              />
            </div>
          </div>
          <div className="hardware-api-actions">
            <button className="btn btn-primary" onClick={onCreateSession} disabled={!apiEnabled || createSessionMutation.isPending}>
              Create Session
            </button>
            <span className={`status-badge ${toneClass(actionTone)}`}>● {actionMessage}</span>
          </div>
        </div>
      </div>

      <div className="table-container section-offset">
        <div className="table-wrapper">
          <div className="section-title">Ingest Frames</div>
          <div className="panel-subtitle">
            Payload expects IBM-adapter shape with <code>noise_sample</code>, <code>syndrome_samples</code>, and{" "}
            <code>decoder_interventions</code>.
          </div>
          <div className="hardware-api-editor">
            <textarea
              className="form-textarea hardware-api-textarea"
              value={framePayloadText}
              onChange={(event) => {
                setFramePayloadDirty(true);
                setFramePayloadText(event.target.value);
              }}
              spellCheck={false}
            />
            <div className="hardware-api-actions">
              <button
                className="btn btn-primary"
                onClick={onIngestFrames}
                disabled={!apiEnabled || ingestFramesMutation.isPending || !selectedSession}
              >
                Ingest Frames
              </button>
              <button
                className="btn btn-secondary"
                onClick={onCompleteSession}
                disabled={!apiEnabled || completeSessionMutation.isPending || !selectedSession}
              >
                Complete Session
              </button>
              <span className={`status-badge ${payloadValidation.error ? "status-warning" : "status-success"}`}>
                ● {payloadValidation.error ? `Invalid payload: ${payloadValidation.error}` : "Payload validated"}
              </span>
            </div>
          </div>
          {selectedSession ? (
            <div className="scope-meta">
              Session {selectedSession.id.slice(0, 8)} · Run {selectedSession.run_id.slice(0, 8)} ·{" "}
              {selectedSession.frame_count} frame(s) · {statusLabel(selectedSession.status)}
            </div>
          ) : (
            <div className="scope-meta">No active session selected.</div>
          )}
        </div>
      </div>

      <div className="table-container section-offset">
        <div className="table-wrapper">
          <div className="section-title">Sessions</div>
          <div className="panel-subtitle">Hardware ingestion sessions and their linked runs.</div>
          <table>
            <thead>
              <tr>
                <th>Session</th>
                <th>Run</th>
                <th>Provider</th>
                <th>Mode</th>
                <th>Frames</th>
                <th>Status</th>
                <th>Updated</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {sessions.map((session) => (
                <tr key={session.id}>
                  <td>{session.id.slice(0, 8)}</td>
                  <td>{session.run_id.slice(0, 8)}</td>
                  <td>{providerLookup.get(session.provider_id)?.name ?? session.provider_id.slice(0, 8)}</td>
                  <td>{session.source_mode}</td>
                  <td>{session.frame_count}</td>
                  <td>
                    <span className={`status-badge ${statusClass(session.status)}`}>● {statusLabel(session.status)}</span>
                  </td>
                  <td>{formatAgo(session.updated_at)}</td>
                  <td>
                    <div className="actions">
                      <button className="btn btn-secondary" onClick={() => setActiveSessionId(session.id)}>
                        Use
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {sessions.length === 0 ? (
                <tr>
                  <td colSpan={8}>
                    <span className="muted-inline">No hardware sessions yet.</span>
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>

      <div className="table-container section-offset">
        <div className="table-wrapper">
          <div className="section-title">Schema & cURL</div>
          <div className="panel-subtitle">
            Use these commands to connect an external hardware process to LiDMaS+ with the exact frame schema.
          </div>
          <div className="hardware-api-code-grid">
            <div>
              <div className="hardware-api-code-title">Create Session</div>
              <pre className="hardware-api-code">{curlExamples.createCurl}</pre>
            </div>
            <div>
              <div className="hardware-api-code-title">Ingest Frames</div>
              <pre className="hardware-api-code">{curlExamples.ingestCurl}</pre>
            </div>
            <div>
              <div className="hardware-api-code-title">Complete Session</div>
              <pre className="hardware-api-code">{curlExamples.completeCurl}</pre>
            </div>
          </div>
          <div className="section-title section-offset-inline">Schema Notes</div>
          {schemaQuery.data?.notes?.length ? (
            <ul className="hardware-api-note-list">
              {schemaQuery.data.notes.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          ) : (
            <div className="scope-meta">Schema notes unavailable.</div>
          )}
          {selectedSession ? (
            <div className="scope-meta">
              Linked run status: {runLookup.get(selectedSession.run_id)?.status ?? "unknown"} · Dataset:{" "}
              {selectedSession.dataset_label}
            </div>
          ) : null}
        </div>
      </div>

      {loading ? (
        <div className="empty-card">
          <strong>Loading Hardware API</strong>
          <p>Fetching providers, schema, and session state.</p>
        </div>
      ) : null}

      {error ? (
        <div className="empty-card">
          <strong>Hardware API unavailable</strong>
          <p>Backend endpoints are unavailable or authorization is missing.</p>
        </div>
      ) : null}
    </>
  );
}
