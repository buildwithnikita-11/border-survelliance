// AlertDetail shows detailed information and evidence grouped by source for the selected alert.
export default function AlertDetail({ alert }) {
  // Handle no alert selected state
  if (!alert) {
    return (
      <div style={{ border: '1px solid #ccc', borderRadius: '4px', padding: '16px', marginBottom: '16px' }}>
        <h3 style={{ marginTop: 0 }}>Alert Detail</h3>
        <p>No alert selected.</p>
      </div>
    );
  }

  // Group evidence items by their source
  const evidenceBySource = (alert.evidence || []).reduce((acc, item) => {
    const src = item.source || 'unknown';
    if (!acc[src]) {
      acc[src] = [];
    }
    acc[src].push(item);
    return acc;
  }, {});

  return (
    <div style={{ border: '1px solid #ccc', borderRadius: '4px', padding: '16px', marginBottom: '16px' }}>
      <h3 style={{ marginTop: 0 }}>Alert Detail: {alert.alert_id}</h3>
      <div style={{ marginBottom: '16px', lineHeight: '1.6' }}>
        <div><strong>Status:</strong> {alert.status}</div>
        <div><strong>Score:</strong> {alert.score} / 10</div>
        <div><strong>Window:</strong> {alert.time_window_start} to {alert.time_window_end}</div>
        <div><strong>Analyst Note:</strong> {alert.analyst_note || '(none)'}</div>
      </div>

      <h4 style={{ marginBottom: '8px' }}>Evidence by Source</h4>
      {Object.keys(evidenceBySource).length === 0 ? (
        <p>No evidence items available.</p>
      ) : (
        Object.entries(evidenceBySource).map(([source, items]) => (
          <div
            key={source}
            style={{
              border: '1px solid #e2e8f0',
              backgroundColor: '#f8fafc',
              borderRadius: '4px',
              padding: '12px',
              marginBottom: '12px',
            }}
          >
            <h5 style={{ margin: '0 0 8px 0', textTransform: 'capitalize' }}>Source: {source}</h5>
            {items.map((ev, index) => (
              <div
                key={ev.event_id || index}
                style={{
                  borderTop: index > 0 ? '1px solid #e2e8f0' : 'none',
                  paddingTop: index > 0 ? '8px' : '0',
                  marginTop: index > 0 ? '8px' : '0',
                  fontSize: '0.9em',
                  lineHeight: '1.5',
                }}
              >
                <div><strong>Main Feature:</strong> {ev.main_feature}</div>
                <div><strong>Value:</strong> {ev.value}</div>
                <div><strong>Normal Average:</strong> {ev.normal_average}</div>
                <div><strong>Deviation:</strong> {ev.deviation} std dev</div>
                <div><strong>Confidence:</strong> {ev.confidence}</div>
                <div><strong>Reason:</strong> {ev.reason}</div>
              </div>
            ))}
          </div>
        ))
      )}
    </div>
  );
}
