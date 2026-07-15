interface ReplaySourceOption {
  runId: string;
  datasetLabel: string;
  providerName: string;
  updatedAtLabel: string;
}

interface StartReplaySessionDialogProps {
  open: boolean;
  pending: boolean;
  sources: ReplaySourceOption[];
  selectedSourceRunId: string;
  onSelectSource: (runId: string) => void;
  onClose: () => void;
  onStart: () => void;
  disabledReason?: string | null;
}

export function StartReplaySessionDialog({
  open,
  pending,
  sources,
  selectedSourceRunId,
  onSelectSource,
  onClose,
  onStart,
  disabledReason,
}: StartReplaySessionDialogProps) {
  if (!open) {
    return null;
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal modal-small session-launcher-dialog" onClick={(event) => event.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title">Replay Historical Run</div>
          <button className="modal-close" onClick={onClose}>
            ×
          </button>
        </div>
        <div className="modal-body">
          <p className="session-launcher-dialog-copy">
            Select a completed run in scope and launch a deterministic replay session.
          </p>
          <div className="session-launcher-field">
            <label>Replay Source</label>
            <select
              className="select-field research-select"
              value={selectedSourceRunId}
              onChange={(event) => onSelectSource(event.target.value)}
              disabled={pending || sources.length === 0}
            >
              {sources.length === 0 ? <option value="">No replay source</option> : null}
              {sources.map((source) => (
                <option key={source.runId} value={source.runId}>
                  {source.runId.slice(0, 8).toUpperCase()} · {source.datasetLabel} · {source.providerName} ·{" "}
                  {source.updatedAtLabel}
                </option>
              ))}
            </select>
          </div>
          {disabledReason ? <div className="scientific-muted-note">{disabledReason}</div> : null}
        </div>
        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onClose} disabled={pending}>
            Cancel
          </button>
          <button className="btn btn-primary" onClick={onStart} disabled={pending || Boolean(disabledReason)}>
            {pending ? "Starting..." : "Start Replay Session"}
          </button>
        </div>
      </div>
    </div>
  );
}
