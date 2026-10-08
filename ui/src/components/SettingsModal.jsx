import { useState, useEffect } from 'react';
import { checkBackendHealth } from '../services/api';

function SettingsModalDialog({
  onClose,
  settings,
  onSaveSettings,
  onClearAllChats,
}) {
  const [endpoint, setEndpoint] = useState(settings?.apiEndpoint || 'http://localhost:8000');
  const [testStatus, setTestStatus] = useState('idle');
  const [testMessage, setTestMessage] = useState('');

  // Handle Escape key to dismiss
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  const handleTestConnection = async () => {
    setTestStatus('testing');
    setTestMessage('Pinging /api/health...');

    try {
      const data = await checkBackendHealth(endpoint);
      setTestStatus('success');
      setTestMessage(`Backend Connected: ${data.service || 'pluto-api'} (Status: ${data.status})`);
    } catch (err) {
      setTestStatus('error');
      setTestMessage(err.message || 'Connection failed.');
    }
  };

  const handleSave = () => {
    onSaveSettings({
      ...settings,
      apiEndpoint: endpoint.trim() || 'http://localhost:8000',
    });
    onClose();
  };

  const handleBackdropClick = (e) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  const handleClearHistory = () => {
    const confirmed = window.confirm(
      'Are you sure you want to clear all chat sessions? This cannot be undone.'
    );
    if (confirmed) {
      onClearAllChats();
      onClose();
    }
  };

  return (
    <div
      className="modal-backdrop"
      onClick={handleBackdropClick}
      role="dialog"
      aria-modal="true"
      aria-labelledby="settings-modal-title"
    >
      <div className="modal-card">
        {/* Modal Header */}
        <div className="modal-header">
          <h2 id="settings-modal-title" className="modal-title">
            Settings
          </h2>
          <button
            type="button"
            className="modal-close-btn"
            onClick={onClose}
            aria-label="Close settings modal"
          >
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        {/* Modal Body */}
        <div className="modal-body">
          {/* API Endpoint Section */}
          <div className="form-group">
            <label htmlFor="api-endpoint-input" className="form-label">
              FastAPI Backend URL
            </label>
            <div className="form-row">
              <input
                id="api-endpoint-input"
                type="text"
                className="form-input"
                value={endpoint}
                onChange={(e) => {
                  setEndpoint(e.target.value);
                  setTestStatus('idle');
                }}
                placeholder="http://localhost:8000"
              />
              <button
                type="button"
                className="btn-secondary"
                onClick={handleTestConnection}
                disabled={testStatus === 'testing'}
              >
                {testStatus === 'testing' ? 'Testing...' : 'Test Connection'}
              </button>
            </div>
            {testStatus === 'success' && (
              <div className="status-badge success">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
                <span>{testMessage}</span>
              </div>
            )}
            {testStatus === 'error' && (
              <div className="status-badge error">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <circle cx="12" cy="12" r="10" />
                  <line x1="12" y1="8" x2="12" y2="12" />
                  <line x1="12" y1="16" x2="12.01" y2="16" />
                </svg>
                <span>{testMessage}</span>
              </div>
            )}
            {testStatus === 'testing' && (
              <div className="status-badge info">
                <span>{testMessage}</span>
              </div>
            )}
            <span className="form-helper">
              Standard local endpoint for the Pluto FastAPI server running api.py.
            </span>
          </div>

          {/* Model Engine Section */}
          <div className="form-group">
            <span className="form-label">Model and Agent Engine</span>
            <input
              type="text"
              className="form-input"
              value="Pluto Local Orchestrator v1 (FastAPI backend)"
              disabled
              readOnly
            />
            <span className="form-helper">
              Coordinates perception, reasoning, tool loop, and verification.
            </span>
          </div>

          {/* Theme Confirmation Section */}
          <div className="form-group">
            <span className="form-label">Theme Preference</span>
            <input
              type="text"
              className="form-input"
              value="Light Minimalist (Standard AI Agent)"
              disabled
              readOnly
            />
            <span className="form-helper">
              Milestone 2 standardized white canvas and slate interface.
            </span>
          </div>

          {/* Storage Section */}
          <div className="form-group">
            <span className="form-label">Chat Data Management</span>
            <div>
              <button
                type="button"
                className="btn-danger"
                onClick={handleClearHistory}
              >
                Clear All Chat History
              </button>
            </div>
            <span className="form-helper">
              Permanently removes all saved chat sessions from browser localStorage.
            </span>
          </div>
        </div>

        {/* Modal Footer */}
        <div className="modal-footer">
          <button
            type="button"
            className="btn-secondary"
            onClick={onClose}
          >
            Cancel
          </button>
          <button
            type="button"
            className="btn-primary"
            onClick={handleSave}
          >
            Save Changes
          </button>
        </div>
      </div>
    </div>
  );
}

export default function SettingsModal({
  isOpen,
  onClose,
  settings,
  onSaveSettings,
  onClearAllChats,
}) {
  if (!isOpen) return null;

  return (
    <SettingsModalDialog
      onClose={onClose}
      settings={settings}
      onSaveSettings={onSaveSettings}
      onClearAllChats={onClearAllChats}
    />
  );
}
