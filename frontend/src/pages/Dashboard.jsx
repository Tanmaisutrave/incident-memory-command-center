import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Brain, Database, TrendingUp, AlertCircle, ArrowRight, Activity, CheckCircle } from 'lucide-react';
import LoadingSpinner from '../components/common/LoadingSpinner';
import { api } from '../services/api';

export default function Dashboard() {
  const navigate = useNavigate();
  const [memoryStats, setMemoryStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const stats = await api.getMemoryStats();
        setMemoryStats(stats);
      } catch (error) {
        console.error('Failed to fetch data:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <LoadingSpinner size="lg" text="Loading Command Center..." />
      </div>
    );
  }

  return (
    <div className="p-8 space-y-8">
      {/* Hero Section */}
      <div>
        <h2 className="text-3xl font-bold text-white mb-2">Command Center</h2>
        <p className="text-slate-400">
          Monitor incident response with AI-powered memory assistance
        </p>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard
          icon={Database}
          label="Historical Incidents"
          value={memoryStats?.total_retains || 0}
          description="Stored in memory"
          color="primary"
        />
        <StatCard
          icon={Brain}
          label="Memory Recalls"
          value={memoryStats?.total_recalls || 0}
          description="Searches performed"
          color="purple"
        />
        <StatCard
          icon={Activity}
          label="Memory Bank"
          value={memoryStats?.bank_id || 'incident-agent'}
          description="Active bank"
          color="cyan"
          valueClass="text-lg"
        />
        <StatCard
          icon={TrendingUp}
          label="Learning Status"
          value="Active"
          description="Agent is learning"
          color="green"
        />
      </div>

      {/* Learning Flow Visualization */}
      <div className="bg-gradient-to-br from-primary/10 to-purple-500/10 border-2 border-primary/50 rounded-lg p-8">
        <h3 className="text-2xl font-bold text-white mb-6 text-center">
          🧠 The Memory Learning Cycle
        </h3>
        
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4 relative">
          {/* Step 1 */}
          <div className="relative">
            <div className="bg-surface border-2 border-primary/50 rounded-lg p-4 text-center">
              <div className="w-12 h-12 bg-primary/20 rounded-full flex items-center justify-center mx-auto mb-3">
                <AlertCircle className="w-6 h-6 text-primary" />
              </div>
              <h4 className="text-sm font-bold text-white mb-1">1. ANALYZE</h4>
              <p className="text-xs text-slate-400">Current incident symptoms</p>
            </div>
            <div className="hidden md:block absolute top-1/2 -right-2 transform -translate-y-1/2 text-primary text-2xl z-10">
              →
            </div>
          </div>

          {/* Step 2 */}
          <div className="relative">
            <div className="bg-surface border-2 border-cyan-500/50 rounded-lg p-4 text-center">
              <div className="w-12 h-12 bg-cyan-500/20 rounded-full flex items-center justify-center mx-auto mb-3">
                <Brain className="w-6 h-6 text-cyan-400 animate-pulse" />
              </div>
              <h4 className="text-sm font-bold text-white mb-1">2. RECALL</h4>
              <p className="text-xs text-slate-400">Search historical data</p>
            </div>
            <div className="hidden md:block absolute top-1/2 -right-2 transform -translate-y-1/2 text-primary text-2xl z-10">
              →
            </div>
          </div>

          {/* Step 3 */}
          <div className="relative">
            <div className="bg-surface border-2 border-purple-500/50 rounded-lg p-4 text-center">
              <div className="w-12 h-12 bg-purple-500/20 rounded-full flex items-center justify-center mx-auto mb-3">
                <Database className="w-6 h-6 text-purple-400" />
              </div>
              <h4 className="text-sm font-bold text-white mb-1">3. REASON</h4>
              <p className="text-xs text-slate-400">Evidence-based analysis</p>
            </div>
            <div className="hidden md:block absolute top-1/2 -right-2 transform -translate-y-1/2 text-primary text-2xl z-10">
              →
            </div>
          </div>

          {/* Step 4 */}
          <div className="relative">
            <div className="bg-surface border-2 border-green-500/50 rounded-lg p-4 text-center">
              <div className="w-12 h-12 bg-green-500/20 rounded-full flex items-center justify-center mx-auto mb-3">
                <CheckCircle className="w-6 h-6 text-green-400" />
              </div>
              <h4 className="text-sm font-bold text-white mb-1">4. RESOLVE</h4>
              <p className="text-xs text-slate-400">Incident fixed</p>
            </div>
            <div className="hidden md:block absolute top-1/2 -right-2 transform -translate-y-1/2 text-primary text-2xl z-10">
              →
            </div>
          </div>

          {/* Step 5 */}
          <div className="relative">
            <div className="bg-surface border-2 border-yellow-500/50 rounded-lg p-4 text-center">
              <div className="w-12 h-12 bg-yellow-500/20 rounded-full flex items-center justify-center mx-auto mb-3">
                <TrendingUp className="w-6 h-6 text-yellow-400" />
              </div>
              <h4 className="text-sm font-bold text-white mb-1">5. REMEMBER</h4>
              <p className="text-xs text-slate-400">Store for future</p>
            </div>
          </div>
        </div>

        <div className="mt-6 text-center">
          <div className="inline-block bg-cyan-500/10 border border-cyan-500/30 rounded-lg px-4 py-2">
            <p className="text-sm text-cyan-300">
              <strong>Result:</strong> Each resolved incident improves future recommendations
            </p>
          </div>
        </div>
      </div>

      {/* Learning Explanation */}
      <div className="bg-surface-secondary border border-border rounded-lg p-6">
        <h3 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
          <Brain className="w-6 h-6 text-primary" />
          How the Agent Learns
        </h3>
        
        <div className="space-y-6">
          <div className="flex items-start gap-4">
            <div className="flex-shrink-0 w-10 h-10 bg-primary/20 rounded-lg flex items-center justify-center">
              <AlertCircle className="w-5 h-5 text-primary" />
            </div>
            <div>
              <h4 className="font-semibold text-white mb-1">1. Incident Analysis</h4>
              <p className="text-sm text-slate-400">
                When you analyze an incident, the agent searches Hindsight memory for similar historical incidents
              </p>
            </div>
          </div>

          <div className="flex items-start gap-4">
            <div className="flex-shrink-0 w-10 h-10 bg-purple-500/20 rounded-lg flex items-center justify-center">
              <Database className="w-5 h-5 text-purple-400" />
            </div>
            <div>
              <h4 className="font-semibold text-white mb-1">2. Historical Context</h4>
              <p className="text-sm text-slate-400">
                Previous incidents, their root causes, and successful resolutions inform the current analysis
              </p>
            </div>
          </div>

          <div className="flex items-start gap-4">
            <div className="flex-shrink-0 w-10 h-10 bg-green-500/20 rounded-lg flex items-center justify-center">
              <Brain className="w-5 h-5 text-green-400" />
            </div>
            <div>
              <h4 className="font-semibold text-white mb-1">3. Memory Retention</h4>
              <p className="text-sm text-slate-400">
                When you resolve an incident, the outcome is stored in Hindsight for future reference
              </p>
            </div>
          </div>

          <div className="flex items-start gap-4">
            <div className="flex-shrink-0 w-10 h-10 bg-cyan-500/20 rounded-lg flex items-center justify-center">
              <TrendingUp className="w-5 h-5 text-cyan-400" />
            </div>
            <div>
              <h4 className="font-semibold text-white mb-1">4. Continuous Improvement</h4>
              <p className="text-sm text-slate-400">
                Each resolved incident makes the agent more knowledgeable for future similar problems
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <ActionCard
          title="Analyze New Incident"
          description="Get AI-powered analysis with historical context from Hindsight memory"
          icon={AlertCircle}
          onClick={() => navigate('/analyze')}
          buttonText="Start Analysis"
          color="primary"
        />
        
        <ActionCard
          title="Explore Memory"
          description="Search and discover patterns in historical incident data"
          icon={Brain}
          onClick={() => navigate('/memory')}
          buttonText="Explore Memory"
          color="purple"
        />
      </div>
    </div>
  );
}

function StatCard({ icon: Icon, label, value, description, color, valueClass = 'text-3xl' }) {
  const colorClasses = {
    primary: 'bg-primary/10 text-primary border-primary/30',
    purple: 'bg-purple-500/10 text-purple-400 border-purple-500/30',
    cyan: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30',
    green: 'bg-green-500/10 text-green-400 border-green-500/30',
  };

  return (
    <div className={`bg-surface border rounded-lg p-6 ${colorClasses[color] || colorClasses.primary}`}>
      <Icon className="w-8 h-8 mb-3" />
      <div className={`font-bold mb-1 ${valueClass}`}>{value}</div>
      <div className="text-sm font-semibold text-white mb-1">{label}</div>
      <div className="text-xs text-slate-400">{description}</div>
    </div>
  );
}

function ActionCard({ title, description, icon: Icon, onClick, buttonText, color }) {
  const colorClasses = {
    primary: 'bg-primary hover:bg-primary-hover',
    purple: 'bg-purple-600 hover:bg-purple-700',
  };

  return (
    <div className="bg-surface border border-border rounded-lg p-6 hover:border-primary/50 transition-colors">
      <Icon className="w-10 h-10 text-primary mb-4" />
      <h3 className="text-lg font-semibold text-white mb-2">{title}</h3>
      <p className="text-sm text-slate-400 mb-4">{description}</p>
      <button
        onClick={onClick}
        className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg text-white font-medium transition-colors ${colorClasses[color]}`}
      >
        {buttonText}
        <ArrowRight className="w-4 h-4" />
      </button>
    </div>
  );
}
