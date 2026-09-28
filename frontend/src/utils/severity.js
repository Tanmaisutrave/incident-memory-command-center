/**
 * Severity utilities
 */

export const SEVERITY_CONFIG = {
  P1: {
    label: 'Critical',
    color: 'text-red-400',
    bg: 'bg-red-950',
    border: 'border-red-800',
    description: 'Production down',
  },
  P2: {
    label: 'High',
    color: 'text-orange-400',
    bg: 'bg-orange-950',
    border: 'border-orange-800',
    description: 'Major functionality impaired',
  },
  P3: {
    label: 'Medium',
    color: 'text-yellow-400',
    bg: 'bg-yellow-950',
    border: 'border-yellow-800',
    description: 'Partial functionality impaired',
  },
  P4: {
    label: 'Low',
    color: 'text-gray-400',
    bg: 'bg-gray-950',
    border: 'border-gray-800',
    description: 'Minor issue',
  },
};

export function getSeverityConfig(severity) {
  return SEVERITY_CONFIG[severity] || SEVERITY_CONFIG.P4;
}

export function getSeverityBadgeClass(severity) {
  const config = getSeverityConfig(severity);
  return `${config.color} ${config.bg} ${config.border} border px-3 py-1 rounded text-sm font-medium`;
}
