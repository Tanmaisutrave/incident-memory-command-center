import { NavLink } from 'react-router-dom';
import { 
  LayoutDashboard, 
  AlertCircle, 
  Brain, 
  TrendingUp, 
  Activity,
  GitCompare
} from 'lucide-react';

const navigation = [
  { name: 'Command Center', to: '/', icon: LayoutDashboard },
  { name: 'Analyze Incident', to: '/analyze', icon: AlertCircle },
  { name: 'Memory Explorer', to: '/memory', icon: Brain },
  { name: 'Learning Center', to: '/learning', icon: TrendingUp },
  { name: 'Compare', to: '/compare', icon: GitCompare },
];

export default function Sidebar({ systemHealth }) {
  return (
    <aside className="w-64 bg-surface border-r border-border flex flex-col">
      {/* Logo */}
      <div className="p-6 border-b border-border">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-primary/20 rounded-lg flex items-center justify-center">
            <Brain className="w-6 h-6 text-primary" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-white">Command Center</h1>
            <p className="text-xs text-slate-400">Incident Memory</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4 space-y-1">
        {navigation.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              `flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
                isActive
                  ? 'bg-primary/10 text-primary'
                  : 'text-slate-400 hover:text-white hover:bg-surface-secondary'
              }`
            }
          >
            <item.icon className="w-5 h-5" />
            <span className="font-medium">{item.name}</span>
          </NavLink>
        ))}
      </nav>

      {/* System Status */}
      <div className="p-4 border-t border-border">
        <h3 className="text-xs font-semibold text-slate-500 mb-3 uppercase tracking-wider">
          System Status
        </h3>
        <div className="space-y-2">
          <StatusIndicator 
            label="Hindsight" 
            status={systemHealth?.hindsight_status} 
          />
          <StatusIndicator 
            label="AI Engine" 
            status={systemHealth?.groq_status} 
          />
          <StatusIndicator 
            label="API" 
            status={systemHealth?.status} 
          />
        </div>
      </div>
    </aside>
  );
}

function StatusIndicator({ label, status }) {
  const isHealthy = status === 'healthy' || status === 'operational';
  
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-slate-400">{label}</span>
      <div className="flex items-center gap-2">
        <div className={`w-2 h-2 rounded-full ${isHealthy ? 'bg-green-400' : 'bg-red-400'}`} />
        <span className={isHealthy ? 'text-green-400' : 'text-red-400'}>
          {isHealthy ? 'Connected' : 'Unavailable'}
        </span>
      </div>
    </div>
  );
}
