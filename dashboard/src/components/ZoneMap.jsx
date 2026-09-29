import React from 'react';

// Fixed zones defined in schema.md section 3
const ZONES = ['zone_1', 'zone_2', 'zone_3'];

// ZoneMap displays a fictional 3-cell grid for zone_1, zone_2, and zone_3.
// Colors a cell if a pending alert exists in that zone (stronger color for higher score).
export default function ZoneMap({ alerts = [], selectedAlert, onSelectAlert, onSelect }) {
  const handleSelect = onSelectAlert || onSelect;

  // Calculate cell color based on presence of pending alerts and maximum score
  const getZoneStyle = (zone) => {
    const pendingAlerts = (alerts || []).filter(
      (a) => a.zone === zone && a.status === 'pending'
    );
    const hasPending = pendingAlerts.length > 0;
    const isSelected = selectedAlert && selectedAlert.zone === zone;

    if (!hasPending) {
      return {
        backgroundColor: '#f1f5f9',
        border: isSelected ? '2px solid #2563eb' : '1px solid #cbd5e1',
        color: '#475569',
      };
    }

    // Highest score among pending alerts in this zone (0-10)
    const maxScore = Math.max(...pendingAlerts.map((a) => Number(a.score) || 0));
    // Color intensity scales from 0.2 to 0.85 opacity based on score
    const alpha = 0.2 + (Math.min(Math.max(maxScore, 0), 10) / 10) * 0.65;

    return {
      backgroundColor: `rgba(239, 68, 68, ${alpha})`,
      border: isSelected ? '2px solid #2563eb' : '1px solid #dc2626',
      color: alpha > 0.5 ? '#ffffff' : '#991b1b',
    };
  };

  // Click handler: select that zone's newest alert
  const handleZoneClick = (zone) => {
    const zoneAlerts = (alerts || []).filter((a) => a.zone === zone);
    if (zoneAlerts.length > 0 && handleSelect) {
      // Sort newest first by created_at in case alerts wasn't pre-sorted
      const sorted = [...zoneAlerts].sort((a, b) =>
        (b.created_at || '').localeCompare(a.created_at || '')
      );
      handleSelect(sorted[0]);
    }
  };

  return (
    <div style={{ border: '1px solid #ccc', borderRadius: '4px', padding: '16px', marginBottom: '16px' }}>
      <h3 style={{ marginTop: 0 }}>Zone Map</h3>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px' }}>
        {ZONES.map((zone) => {
          const pendingAlerts = (alerts || []).filter(
            (a) => a.zone === zone && a.status === 'pending'
          );
          const maxScore =
            pendingAlerts.length > 0
              ? Math.max(...pendingAlerts.map((a) => Number(a.score) || 0))
              : null;
          const style = getZoneStyle(zone);

          return (
            <div
              key={zone}
              id={`zone-cell-${zone}`}
              onClick={() => handleZoneClick(zone)}
              style={{
                ...style,
                padding: '16px',
                borderRadius: '6px',
                textAlign: 'center',
                cursor: 'pointer',
                transition: 'all 0.2s',
              }}
            >
              <div style={{ fontWeight: 'bold', fontSize: '1.1em', marginBottom: '6px' }}>
                {zone}
              </div>
              {pendingAlerts.length > 0 ? (
                <div>
                  <div style={{ fontSize: '0.9em' }}>
                    {pendingAlerts.length} Pending
                  </div>
                  <div style={{ fontSize: '0.85em', fontWeight: 'bold' }}>
                    Max Score: {maxScore}
                  </div>
                </div>
              ) : (
                <div style={{ fontSize: '0.85em' }}>Normal</div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
