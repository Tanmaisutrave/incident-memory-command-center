import { useState } from 'react';
import { CheckCircle, XCircle, AlertCircle, Brain, Database, Sparkles } from 'lucide-react';
import LoadingSpinner from '../common/LoadingSpinner';
import ErrorMessage from '../common/ErrorMessage';

export default function ResolutionForm({ incidentId, onResolutionComplete, onCancel, onSuccess }) {
  const [formData, setFormData] = useState({
    root_cause: '',
    resolution: '',
    actions_taken: '',
    lessons_learned: '',
    outcome: 'successfully_resolved'
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [resolved, setResolved] = useState(false);
  const [retainedData, setRetainedData] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      // Prepare data in backend format
      const requestData = {
        root_cause: formData.root_cause,
        actions_taken: formData.actions_taken.split('\n').filter(line => line.trim()),
        resolution: formData.resolution,
        outcome: formData.outcome,
        lessons_learned: formData.lessons_learned || undefined
      };

      const response = await fetch(
        `${import.meta.env.VITE_API_BASE_URL}/api/incidents/${incidentId}/resolve`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(requestData)
        }
      );

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to resolve incident');
      }

      const result = await response.json();
      setRetainedData(result);
      setResolved(true);
      
      // Call callbacks
      if (onResolutionComplete) onResolutionComplete(result);
      if (onSuccess) onSuccess(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Success screen after resolution
  if (resolved && retainedData) {
    return (
      <div className="bg-gradient-to-br from-green-500/10 to-cyan-500/10 border-2 border-green-500/50 rounded-lg p-8 text-center">
        <div className="flex justify-center mb-6">
          <div className="w-20 h-20 bg-green-500/20 rounded-full flex items-center justify-center">
            <CheckCircle className="w-12 h-12 text-green-400" />
          </div>
        </div>
        
        <h3 className="text-2xl font-bold text-white mb-2">✅ INCIDENT RESOLVED</h3>
        <p className="text-slate-300 mb-8">The incident has been successfully resolved and documented</p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
          <div className="bg-surface/50 border border-green-500/30 rounded-lg p-4">
            <Database className="w-8 h-8 text-green-400 mx-auto mb-2" />
            <div className="text-sm text-slate-400 mb-1">Resolution</div>
            <div className="text-lg font-semibold text-white">Documented</div>
          </div>
          
          <div className="bg-surface/50 border border-cyan-500/30 rounded-lg p-4">
            <Brain className="w-8 h-8 text-cyan-400 mx-auto mb-2 animate-pulse" />
            <div className="text-sm text-slate-400 mb-1">Memory</div>
            <div className="text-lg font-semibold text-white">Retained</div>
          </div>
          
          <div className="bg-surface/50 border border-purple-500/30 rounded-lg p-4">
            <Sparkles className="w-8 h-8 text-purple-400 mx-auto mb-2" />
            <div className="text-sm text-slate-400 mb-1">Status</div>
            <div className="text-lg font-semibold text-white capitalize">{formData.outcome}</div>
          </div>
        </div>

        <div className="bg-cyan-500/10 border border-cyan-500/30 rounded-lg p-6 mb-6">
          <h4 className="text-lg font-semibold text-cyan-400 mb-3 flex items-center justify-center gap-2">
            <Brain className="w-5 h-5" />
            🧠 LESSON RETAINED IN HINDSIGHT MEMORY
          </h4>
          
          <div className="text-left space-y-3 text-sm">
            <div>
              <span className="text-slate-400 font-semibold">✓ Incident Context:</span>
              <span className="text-slate-300 ml-2">Symptoms, severity, and environment captured</span>
            </div>
            <div>
              <span className="text-slate-400 font-semibold">✓ Root Cause:</span>
              <span className="text-slate-300 ml-2">Identified and documented</span>
            </div>
            <div>
              <span className="text-slate-400 font-semibold">✓ Resolution Actions:</span>
              <span className="text-slate-300 ml-2">Stored for future reference</span>
            </div>
            <div>
              <span className="text-slate-400 font-semibold">✓ Outcome & Impact:</span>
              <span className="text-slate-300 ml-2">Results recorded</span>
            </div>
            <div>
              <span className="text-slate-400 font-semibold">✓ Lessons Learned:</span>
              <span className="text-slate-300 ml-2">Available for future incidents</span>
            </div>
          </div>
        </div>

        <div className="bg-primary/10 border border-primary/30 rounded-lg p-4 mb-6">
          <p className="text-sm text-primary font-medium">
            🚀 Future incidents with similar symptoms will now benefit from this experience
          </p>
        </div>

        <button
          onClick={() => {
            setResolved(false);
            if (onCancel) onCancel();
          }}
          className="px-6 py-3 bg-primary hover:bg-cyan-600 text-white rounded-lg font-semibold transition-colors"
        >
          Close
        </button>
      </div>
    );
  }

  const outcomeOptions = [
    { value: 'successfully_resolved', label: 'Resolved', icon: CheckCircle, color: 'text-green-400' },
    { value: 'partially_resolved', label: 'Mitigated', icon: AlertCircle, color: 'text-yellow-400' },
    { value: 'unresolved_escalated', label: 'Unresolved', icon: XCircle, color: 'text-red-400' }
  ];

  return (
    <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-xl font-semibold text-white">
          ✅ Resolve & Remember
        </h3>
        <span className="text-xs text-slate-400">All fields required</span>
      </div>

      {error && <ErrorMessage message={error} />}

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Outcome Selection */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            Outcome *
          </label>
          <div className="grid grid-cols-3 gap-3">
            {outcomeOptions.map(({ value, label, icon: Icon, color }) => (
              <button
                key={value}
                type="button"
                onClick={() => setFormData({ ...formData, outcome: value })}
                className={`
                  p-3 rounded-lg border-2 transition-all
                  ${formData.outcome === value
                    ? 'border-cyan-500 bg-cyan-500/10'
                    : 'border-gray-700 bg-gray-900 hover:border-gray-600'
                  }
                `}
              >
                <Icon className={`w-5 h-5 mx-auto mb-1 ${color}`} />
                <div className="text-sm font-medium text-white">{label}</div>
              </button>
            ))}
          </div>
        </div>

        {/* Root Cause */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            Root Cause *
          </label>
          <textarea
            value={formData.root_cause}
            onChange={(e) => setFormData({ ...formData, root_cause: e.target.value })}
            placeholder="What was the root cause of this incident?"
            className="w-full px-4 py-2 bg-gray-900 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500"
            rows={3}
            required
          />
        </div>

        {/* Resolution */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            Resolution *
          </label>
          <textarea
            value={formData.resolution}
            onChange={(e) => setFormData({ ...formData, resolution: e.target.value })}
            placeholder="How was the incident resolved?"
            className="w-full px-4 py-2 bg-gray-900 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500"
            rows={3}
            required
          />
        </div>

        {/* Actions Taken */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            Actions Taken * <span className="text-xs text-slate-400">(one per line)</span>
          </label>
          <textarea
            value={formData.actions_taken}
            onChange={(e) => setFormData({ ...formData, actions_taken: e.target.value })}
            placeholder="List the specific actions taken (one per line):&#10;1. Identified connection pool exhaustion&#10;2. Increased pool size to 250&#10;3. Restarted service"
            className="w-full px-4 py-2 bg-gray-900 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500"
            rows={4}
            required
          />
        </div>

        {/* Lessons Learned */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            Lessons Learned
          </label>
          <textarea
            value={formData.lessons_learned}
            onChange={(e) => setFormData({ ...formData, lessons_learned: e.target.value })}
            placeholder="What did we learn? What should we do differently next time?"
            className="w-full px-4 py-2 bg-gray-900 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500"
            rows={3}
          />
        </div>

        {/* Submit Buttons */}
        <div className="flex justify-end space-x-3 pt-4">
          {onCancel && (
            <button
              type="button"
              onClick={onCancel}
              className="px-6 py-2 bg-gray-700 text-white rounded-lg hover:bg-gray-600 transition-colors font-medium"
            >
              Cancel
            </button>
          )}
          <button
            type="submit"
            disabled={loading}
            className="px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium flex items-center space-x-2"
          >
            {loading ? (
              <>
                <LoadingSpinner size="small" />
                <span>Resolving & Retaining...</span>
              </>
            ) : (
              <>
                <CheckCircle className="w-5 h-5" />
                <span>Resolve & Remember</span>
              </>
            )}
          </button>
        </div>
      </form>

      <div className="mt-4 p-4 bg-gradient-to-r from-cyan-500/10 to-purple-500/10 border border-cyan-500/30 rounded-lg">
        <div className="flex items-start gap-3">
          <Brain className="w-5 h-5 text-cyan-400 flex-shrink-0 mt-0.5" />
          <div>
            <h5 className="text-sm font-semibold text-cyan-400 mb-1">🧠 Memory Integration</h5>
            <p className="text-xs text-slate-300">
              When you complete this resolution, the agent will <strong>RETAIN</strong> this incident 
              in Hindsight memory. Future similar incidents will <strong>RECALL</strong> this solution 
              and provide evidence-based recommendations.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
