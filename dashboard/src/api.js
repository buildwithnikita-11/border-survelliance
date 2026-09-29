// Base URL for alert API service (Person 3 backend)
export const BASE_URL = 'http://localhost:8001';

// Handle fetch response and throw real error including HTTP status
async function handleResponse(response) {
  if (!response.ok) {
    let detail = '';
    try {
      const data = await response.json();
      detail = data.detail ? (typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)) : JSON.stringify(data);
    } catch {
      detail = await response.text();
    }
    throw new Error(`HTTP ${response.status} ${response.statusText}: ${detail}`);
  }
  return response.json();
}

// List alerts with optional status filter
export async function listAlerts(status) {
  const url = status
    ? `${BASE_URL}/alerts?status=${encodeURIComponent(status)}`
    : `${BASE_URL}/alerts`;
  const response = await fetch(url);
  return handleResponse(response);
}

// Get single alert by ID
export async function getAlert(id) {
  const response = await fetch(`${BASE_URL}/alerts/${encodeURIComponent(id)}`);
  return handleResponse(response);
}

// Update alert status and analyst note via PATCH
export async function updateAlert(id, status, note) {
  const response = await fetch(`${BASE_URL}/alerts/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      status,
      analyst_note: note,
    }),
  });
  return handleResponse(response);
}
