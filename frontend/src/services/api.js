/**
 * API Service Layer
 * Centralized API communication with the backend
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

class APIError extends Error {
  constructor(message, status, data) {
    super(message);
    this.name = 'APIError';
    this.status = status;
    this.data = data;
  }
}

async function handleResponse(response) {
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new APIError(
      data.detail || `HTTP Error ${response.status}`,
      response.status,
      data
    );
  }
  return response.json();
}

async function request(endpoint, options = {}) {
  const url = `${API_BASE_URL}${endpoint}`;
  const config = {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  };

  try {
    const response = await fetch(url, config);
    return await handleResponse(response);
  } catch (error) {
    if (error instanceof APIError) {
      throw error;
    }
    throw new APIError('Network error or server unavailable', 0, { original: error.message });
  }
}

export const api = {
  // Health Check
  async getHealth() {
    return request('/api/health');
  },

  // Incident Operations
  async analyzeIncident(incidentData) {
    return request('/api/incidents/analyze', {
      method: 'POST',
      body: JSON.stringify(incidentData),
    });
  },

  async compareIncident(incidentData) {
    return request('/api/incidents/compare', {
      method: 'POST',
      body: JSON.stringify({ incident: incidentData }),
    });
  },

  async getIncident(incidentId) {
    return request(`/api/incidents/${incidentId}`);
  },

  async getIncidentMemories(incidentId) {
    return request(`/api/incidents/${incidentId}/memories`);
  },

  async resolveIncident(incidentId, resolutionData) {
    return request(`/api/incidents/${incidentId}/resolve`, {
      method: 'POST',
      body: JSON.stringify(resolutionData),
    });
  },

  // Memory Operations
  async recallMemory(query, maxTokens = 4096, budget = 'mid') {
    return request('/api/memory/recall', {
      method: 'POST',
      body: JSON.stringify({
        query,
        max_tokens: maxTokens,
        budget,
      }),
    });
  },

  async reflectMemory(query, budget = 'mid') {
    return request('/api/memory/reflect', {
      method: 'POST',
      body: JSON.stringify({
        query,
        budget,
      }),
    });
  },

  async getMemoryStats() {
    return request('/api/memory/stats');
  },
};

export { APIError };
