import React, { useState, useEffect, useCallback } from 'react';
import { listAlerts } from './api';
import AlertList from './components/AlertList';
import ZoneMap from './components/ZoneMap';
import AlertDetail from './components/AlertDetail';
import ReviewControls from './components/ReviewControls';

export default function App() {
  const [alerts, setAlerts] = useState([]);
  const [selectedAlert, setSelectedAlert] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Fetch alerts from API and keep selected alert in sync
  const fetchAlerts = useCallback(async () => {
    try {
      const data = await listAlerts();
      setAlerts(data);
      setError(null);

      // Keep selected alert updated or pick the first available
      setSelectedAlert((current) => {
        if (!current) {
          return data.length > 0 ? data[0] : null;
        }
        const updated = data.find((a) => a.alert_id === current.alert_id);
        return updated || (data.length > 0 ? data[0] : null);
      });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  // Poll alerts every 5 seconds
  useEffect(() => {
    fetchAlerts();
    const interval = setInterval(fetchAlerts, 5000);
    return () => clearInterval(interval);
  }, [fetchAlerts]);

  return (
    <div style={{ padding: '20px', fontFamily: 'sans-serif' }}>
      <h1>Border Surveillance Dashboard</h1>

      {loading && <div id="loading">Loading alerts...</div>}

      {error && (
        <div
          id="error-message"
          style={{
            padding: '12px',
            marginBottom: '16px',
            backgroundColor: '#fee2e2',
            border: '1px solid #ef4444',
            color: '#b91c1c',
            borderRadius: '4px',
          }}
        >
          <strong>API Error: </strong>
          <span>{error}</span>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
        <div>
          <AlertList
            alerts={alerts}
            selectedAlert={selectedAlert}
            onSelectAlert={setSelectedAlert}
          />
          <ZoneMap alerts={alerts} selectedAlert={selectedAlert} />
        </div>
        <div>
          <AlertDetail alert={selectedAlert} />
          <ReviewControls alert={selectedAlert} onRefresh={fetchAlerts} />
        </div>
      </div>
    </div>
  );
}
