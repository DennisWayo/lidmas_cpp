interface EditProviderModalProps {
  provider: any;
  onClose: () => void;
}

export function EditProviderModal({ provider, onClose }: EditProviderModalProps) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div>
            <div className="modal-title">Edit Provider</div>
            <div className="modal-subtitle">{provider.name}</div>
          </div>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>

        <form onSubmit={(e) => { e.preventDefault(); onClose(); }}>
          <div className="modal-body">
            <div className="status-info">
              ✓ Status: <span className="status-active">Active</span>
            </div>

            <div className="info-box">
              ℹ️ Last connected: 2 hours ago | Health: {provider.health}%
            </div>

            <div className="form-group">
              <label className="form-label required">Provider Name</label>
              <input
                type="text"
                className="form-input"
                defaultValue={provider.name}
                disabled
              />
              <span className="form-hint">Cannot be changed after creation</span>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label className="form-label required">Provider Type</label>
                <select className="form-select" defaultValue={provider.type}>
                  <option>{provider.type}</option>
                </select>
              </div>

              <div className="form-group">
                <label className="form-label required">Location/Region</label>
                <input
                  type="text"
                  className="form-input"
                  defaultValue={provider.region}
                />
              </div>
            </div>

            <div className="form-group">
              <label className="form-label required">API Key / Token</label>
              <input
                type="password"
                className="form-input"
                defaultValue="••••••••••••••••"
              />
              <span className="form-hint">Update to change credentials</span>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label className="form-label">Queue Priority</label>
                <select className="form-select" defaultValue="High">
                  <option>High</option>
                  <option>Normal</option>
                  <option>Low</option>
                </select>
              </div>

              <div className="form-group">
                <label className="form-label">Max Qubits</label>
                <input type="number" className="form-input" defaultValue={256} />
              </div>
            </div>

            <div className="form-group full-width">
              <label className="form-label">Configuration Notes</label>
              <textarea
                className="form-textarea"
                defaultValue={`${provider.type} provider instance for quantum circuit execution. Connected to ${provider.region} region.`}
              />
            </div>
          </div>

          <div className="modal-footer">
            <button type="button" className="btn btn-secondary" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary">
              Save Changes
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
