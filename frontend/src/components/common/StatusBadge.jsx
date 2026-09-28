const statusConfig = {
  reported: { label: 'Reported', color: 'text-blue-400 bg-blue-950 border-blue-800' },
  investigating: { label: 'Investigating', color: 'text-cyan-400 bg-cyan-950 border-cyan-800' },
  diagnosed: { label: 'Diagnosed', color: 'text-purple-400 bg-purple-950 border-purple-800' },
  resolving: { label: 'Resolving', color: 'text-yellow-400 bg-yellow-950 border-yellow-800' },
  resolved: { label: 'Resolved', color: 'text-green-400 bg-green-950 border-green-800' },
  closed: { label: 'Closed', color: 'text-slate-400 bg-slate-950 border-slate-800' },
};

export default function StatusBadge({ status }) {
  const config = statusConfig[status] || statusConfig.reported;
  
  return (
    <span className={`inline-flex items-center px-3 py-1 rounded border text-sm font-medium ${config.color}`}>
      {config.label}
    </span>
  );
}
