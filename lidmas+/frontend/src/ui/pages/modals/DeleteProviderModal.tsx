interface DeleteProviderModalProps {
  provider: any;
  onClose: () => void;
}

export function DeleteProviderModal({ provider, onClose }: DeleteProviderModalProps) {
  const handleDelete = (e: React.FormEvent) => {
    e.preventDefault();
    console.log("Deleting provider:", provider.name);
    onClose();
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal modal-small" onClick={(e) => e.stopPropagation()}>
        <div className="modal-body">
          <div className="modal-icon">⚠</div>

          <div className="modal-title">Delete Provider?</div>

          <div className="modal-message">
            You are about to permanently delete this provider and all associated connections.
          </div>

          <div className="modal-provider">
            {provider.name}
          </div>

          <div className="warning-message">
            ⚠ This action cannot be undone. Any active jobs or scheduled tasks on this provider will be cancelled.
          </div>
        </div>

        <form onSubmit={handleDelete}>
          <div className="modal-footer">
            <button type="button" className="btn btn-secondary" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn btn-danger">
              Delete Provider
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
