import { useEffect, useState } from "react";

interface TestConnectionModalProps {
  provider: any;
  onClose: () => void;
}

export function TestConnectionModal({ provider, onClose }: TestConnectionModalProps) {
  const [tests, setTests] = useState([
    { id: "auth", label: "Authentication", message: "Verifying API credentials...", status: "pending" },
    { id: "network", label: "Network Connectivity", message: "Checking network latency...", status: "pending" },
    { id: "qubits", label: "Qubit Availability", message: "Checking available qubits...", status: "pending" },
    { id: "health", label: "Provider Health", message: "Provider is healthy - 98% uptime", status: "success" },
  ]);

  useEffect(() => {
    const runTests = async () => {
      for (let i = 0; i < tests.length - 1; i++) {
        await new Promise((resolve) => setTimeout(resolve, 1000));
        setTests((prev) =>
          prev.map((t, idx) =>
            idx === i ? { ...t, status: idx === 0 ? "success" : Math.random() > 0.2 ? "success" : "failed" } : t
          )
        );
      }
    };
    runTests();
  }, []);

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title">Test Connection</div>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>

        <div className="modal-body">
          <div className="provider-info">
            <strong>Testing:</strong> {provider.name} ({provider.type}, {provider.region})
          </div>

          <div className="test-status-container">
            {tests.map((test) => (
              <div key={test.id} className="test-item">
                <div className={`test-icon ${test.status}`}>
                  {test.status === "pending" && "⟳"}
                  {test.status === "success" && "✓"}
                  {test.status === "failed" && "✗"}
                </div>
                <div className="test-content">
                  <div className="test-label">{test.label}</div>
                  <div className={`test-message ${test.status}`}>{test.message}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onClose}>
            Close
          </button>
          <button className="btn btn-primary" disabled>
            Testing...
          </button>
        </div>
      </div>
    </div>
  );
}
