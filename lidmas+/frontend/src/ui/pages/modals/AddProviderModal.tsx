import { useState } from "react";

interface AddProviderModalProps {
  onClose: () => void;
}

export function AddProviderModal({ onClose }: AddProviderModalProps) {
  const [formData, setFormData] = useState({
    name: "",
    type: "",
    region: "",
    apiKey: "",
    priority: "Normal",
    maxQubits: 128,
    notes: "",
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    console.log("Adding provider:", formData);
    onClose();
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title">Add New Provider</div>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            <div className="form-group">
              <label className="form-label required">Provider Name</label>
              <input
                type="text"
                className="form-input"
                placeholder="e.g., AWS-Quantum-01"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                required
              />
              <span className="form-hint">A unique identifier for this provider instance</span>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label className="form-label required">Provider Type</label>
                <select
                  className="form-select"
                  value={formData.type}
                  onChange={(e) => setFormData({ ...formData, type: e.target.value })}
                  required
                >
                  <option>Select a provider type...</option>
                  <option>IBM Quantum</option>
                  <option>AWS Braket</option>
                  <option>Google Cirq</option>
                  <option>IonQ</option>
                  <option>Rigetti QPU</option>
                  <option>Classical Simulator</option>
                </select>
              </div>

              <div className="form-group">
                <label className="form-label required">Location/Region</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g., us-east-1"
                  value={formData.region}
                  onChange={(e) => setFormData({ ...formData, region: e.target.value })}
                  required
                />
              </div>
            </div>

            <div className="form-group">
              <label className="form-label required">API Key / Token</label>
              <input
                type="password"
                className="form-input"
                placeholder="••••••••••••••••"
                value={formData.apiKey}
                onChange={(e) => setFormData({ ...formData, apiKey: e.target.value })}
                required
              />
              <span className="form-hint">Your authentication credential (encrypted in storage)</span>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label className="form-label">Queue Priority</label>
                <select
                  className="form-select"
                  value={formData.priority}
                  onChange={(e) => setFormData({ ...formData, priority: e.target.value })}
                >
                  <option>Normal</option>
                  <option>High</option>
                  <option>Low</option>
                </select>
              </div>

              <div className="form-group">
                <label className="form-label">Max Qubits</label>
                <input
                  type="number"
                  className="form-input"
                  value={formData.maxQubits}
                  onChange={(e) => setFormData({ ...formData, maxQubits: parseInt(e.target.value) })}
                />
              </div>
            </div>

            <div className="form-group full-width">
              <label className="form-label">Configuration Notes</label>
              <textarea
                className="form-textarea"
                placeholder="Any additional configuration or notes about this provider..."
                value={formData.notes}
                onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
              />
            </div>

            <div className="info-box">
              ℹ️ API credentials are encrypted and secured. Test connection after creation.
            </div>
          </div>

          <div className="modal-footer">
            <button type="button" className="btn btn-secondary" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary">
              Add Provider
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
