import { Activity } from 'lucide-react';

export default function Header({ memoryStats }) {
  return (
    <header className="bg-surface border-b border-border">
      <div className="px-8 py-4 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">
            Incident Memory Command Center
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            AI-powered incident response with persistent operational memory
          </p>
        </div>
        
        <div className="flex items-center gap-6">
          {memoryStats && (
            <div className="flex items-center gap-3 px-4 py-2 bg-primary/10 border border-primary/30 rounded-lg">
              <Activity className="w-5 h-5 text-primary" />
              <div>
                <div className="text-xs text-slate-400">Memory Bank</div>
                <div className="text-sm font-semibold text-primary">
                  {memoryStats.total_retains || 0} incidents retained
                </div>
              </div>
            </div>
          )}
          
          <div className="px-3 py-1 bg-blue-950 border border-blue-800 rounded text-xs font-medium text-blue-400">
            PRODUCTION
          </div>
        </div>
      </div>
    </header>
  );
}
