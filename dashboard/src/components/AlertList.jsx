// AlertList displays all alerts in the order provided by the API (newest first).
// Highlights the selected row and colors the score (high score = review first).
export default function AlertList({ alerts, selectedAlert, onSelectAlert }) {
  // Handle empty alerts state
  if (!alerts || alerts.length === 0) {
    return (
      <div style={{ border: '1px solid #ccc', borderRadius: '4px', padding: '16px', marginBottom: '16px' }}>
        <h3 style={{ marginTop: 0 }}>Alerts</h3>
        <p>No alerts found.</p>
      </div>
    );
  }

  // Color-code score: higher score = higher review priority
  const getScoreColor = (score) => {
    if (score >= 7) return '#dc2626'; // High (red)
    if (score >= 4) return '#d97706'; // Medium (amber)
    return '#16a34a'; // Low (green)
  };

  return (
    <div style={{ border: '1px solid #ccc', borderRadius: '4px', padding: '16px', marginBottom: '16px' }}>
      <h3 style={{ marginTop: 0 }}>Alerts ({alerts.length})</h3>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ borderBottom: '2px solid #ddd', textAlign: 'left' }}>
            <th style={{ padding: '8px' }}>Zone</th>
            <th style={{ padding: '8px' }}>Type</th>
            <th style={{ padding: '8px' }}>Score</th>
            <th style={{ padding: '8px' }}>Created At</th>
            <th style={{ padding: '8px' }}>Status</th>
          </tr>
        </thead>
        <tbody>
          {alerts.map((alert) => {
            const isSelected = selectedAlert && selectedAlert.alert_id === alert.alert_id;
            return (
              <tr
                key={alert.alert_id}
                onClick={() => onSelectAlert && onSelectAlert(alert)}
                style={{
                  cursor: 'pointer',
                  backgroundColor: isSelected ? '#e0f2fe' : 'transparent',
                  borderBottom: '1px solid #eee',
                  fontWeight: isSelected ? 'bold' : 'normal',
                }}
              >
                <td style={{ padding: '8px' }}>{alert.zone}</td>
                <td style={{ padding: '8px' }}>{alert.type}</td>
                <td style={{ padding: '8px', color: getScoreColor(alert.score), fontWeight: 'bold' }}>
                  {alert.score}
                </td>
                <td style={{ padding: '8px', fontSize: '0.85em' }}>{alert.created_at}</td>
                <td style={{ padding: '8px' }}>{alert.status}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
