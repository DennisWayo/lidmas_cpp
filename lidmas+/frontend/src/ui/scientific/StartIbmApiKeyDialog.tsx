interface StartIbmApiKeyDialogProps {
  open: boolean;
  pending: boolean;
  providerName: string;
  apiKey: string;
  ibmInstance: string;
  sourceMode: "metadata" | "qpu";
  onApiKeyChange: (value: string) => void;
  onIbmInstanceChange: (value: string) => void;
  onSourceModeChange: (value: "metadata" | "qpu") => void;
  onClose: () => void;
  onStart: () => void;
  errorMessage?: string | null;
}

export function StartIbmApiKeyDialog({
  open,
  pending,
  providerName,
  apiKey,
  ibmInstance,
  sourceMode,
  onApiKeyChange,
  onIbmInstanceChange,
  onSourceModeChange,
  onClose,
  onStart,
  errorMessage,
}: StartIbmApiKeyDialogProps) {
  if (!open) {
    return null;
  }

  const disabled = pending || apiKey.trim().length === 0;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal modal-small session-launcher-dialog" onClick={(event) => event.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title">IBM API Key Required</div>
          <button className="modal-close" onClick={onClose} disabled={pending}>
            ×
          </button>
        </div>
        <div className="modal-body">
          <p className="session-launcher-dialog-copy">
            Enter your IBM Quantum API key to start a live session on {providerName}.
          </p>
          <div className="session-launcher-field">
            <label>API Key</label>
            <input
              type="password"
              className="form-input"
              value={apiKey}
              onChange={(event) => onApiKeyChange(event.target.value)}
              placeholder="Paste IBM API key"
              autoComplete="off"
              spellCheck={false}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !disabled) {
                  event.preventDefault();
                  onStart();
                }
              }}
              disabled={pending}
            />
          </div>
          <div className="session-launcher-field">
            <label>IBM Source Mode</label>
            <select
              className="form-select"
              value={sourceMode}
              onChange={(event) => onSourceModeChange(event.target.value as "metadata" | "qpu")}
              disabled={pending}
            >
              <option value="metadata">Non-live noise (metadata polling)</option>
              <option value="qpu">IBM live noise on QPU (submits real jobs)</option>
            </select>
          </div>
          <div className="session-launcher-field">
            <label>IBM Instance (optional)</label>
            <input
              type="text"
              className="form-input"
              value={ibmInstance}
              onChange={(event) => onIbmInstanceChange(event.target.value)}
              placeholder="e.g. qucspec-instance or ibm-q/open/main"
              autoComplete="off"
              spellCheck={false}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !disabled) {
                  event.preventDefault();
                  onStart();
                }
              }}
              disabled={pending}
            />
          </div>
          {sourceMode === "qpu" ? (
            <div className="scientific-muted-note">
              QPU mode runs real sampler jobs on the selected IBM backend and may incur queue time/usage. Add an
              instance to force a specific account scope; otherwise IBM Runtime auto-selects one.
            </div>
          ) : null}
          {errorMessage ? <div className="session-launcher-error">{errorMessage}</div> : null}
        </div>
        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onClose} disabled={pending}>
            Cancel
          </button>
          <button className="btn btn-primary" onClick={onStart} disabled={disabled}>
            {pending ? "Saving..." : "Save and Start Session"}
          </button>
        </div>
      </div>
    </div>
  );
}
