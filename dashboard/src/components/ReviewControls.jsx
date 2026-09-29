import React, { useState, useEffect } from 'react';
import { updateAlert } from '../api';

// ReviewControls provides actions to Confirm, Dismiss, or Flag the selected alert.
// Disables inputs while request is in flight or when no alert is selected.
export default function ReviewControls({ alert, onRefresh, refresh }) {
  const [note, setNote] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const refreshFn = onRefresh || refresh;

  // Sync note text box when selected alert changes
  useEffect(() => {
    setNote(alert?.analyst_note || '');
    setError(null);
  }, [alert?.alert_id]);

  // Handle status update and analyst note submission
  const handleUpdate = async (status) => {
    if (!alert) return;
    setLoading(true);
    setError(null);

    try {
      // Send note or empty string if blank
      await updateAlert(alert.alert_id, status, note || '');
      if (refreshFn) {
        await refreshFn();
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const isDisabled = !alert || loading;

  return (
    <div style={{ border: '1px solid #ccc', borderRadius: '4px', padding: '16px', marginBottom: '16px' }}>
      <h3 style={{ marginTop: 0 }}>Review Controls</h3>

      <div style={{ marginBottom: '12px' }}>
        <label htmlFor="analyst-notes" style={{ display: 'block', fontWeight: 'bold', marginBottom: '4px' }}>
          Analyst Note:
        </label>
        <textarea
          id="analyst-notes"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          disabled={isDisabled}
          placeholder={alert ? 'Enter review notes...' : 'Select an alert to review'}
          rows={3}
          style={{
            width: '100%',
            padding: '8px',
            borderRadius: '4px',
            border: '1px solid #cbd5e1',
            boxSizing: 'border-box',
            fontFamily: 'inherit',
          }}
        />
      </div>

      <div style={{ display: 'flex', gap: '8px' }}>
        <button
          id="btn-confirm"
          type="button"
          onClick={() => handleUpdate('confirmed')}
          disabled={isDisabled}
          style={{
            padding: '8px 16px',
            backgroundColor: isDisabled ? '#94a3b8' : '#16a34a',
            color: '#ffffff',
            border: 'none',
            borderRadius: '4px',
            cursor: isDisabled ? 'not-allowed' : 'pointer',
            fontWeight: 'bold',
          }}
        >
          Confirm
        </button>

        <button
          id="btn-dismiss"
          type="button"
          onClick={() => handleUpdate('dismissed')}
          disabled={isDisabled}
          style={{
            padding: '8px 16px',
            backgroundColor: isDisabled ? '#94a3b8' : '#64748b',
            color: '#ffffff',
            border: 'none',
            borderRadius: '4px',
            cursor: isDisabled ? 'not-allowed' : 'pointer',
            fontWeight: 'bold',
          }}
        >
          Dismiss
        </button>

        <button
          id="btn-flag"
          type="button"
          onClick={() => handleUpdate('flagged')}
          disabled={isDisabled}
          style={{
            padding: '8px 16px',
            backgroundColor: isDisabled ? '#94a3b8' : '#ea580c',
            color: '#ffffff',
            border: 'none',
            borderRadius: '4px',
            cursor: isDisabled ? 'not-allowed' : 'pointer',
            fontWeight: 'bold',
          }}
        >
          Flag
        </button>

        {loading && <span style={{ alignSelf: 'center', marginLeft: '8px' }}>Updating...</span>}
      </div>

      {error && (
        <div
          id="review-error"
          style={{
            marginTop: '12px',
            padding: '8px',
            backgroundColor: '#fee2e2',
            border: '1px solid #ef4444',
            color: '#b91c1c',
            borderRadius: '4px',
            fontSize: '0.9em',
          }}
        >
          <strong>Update Error: </strong>
          <span>{error}</span>
        </div>
      )}
    </div>
  );
}
