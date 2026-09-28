import { useState } from 'react';
import { GitCompare, ArrowRight, Brain, AlertCircle } from 'lucide-react';
import LoadingSpinner from '../components/common/LoadingSpinner';
import ErrorMessage from '../components/common/ErrorMessage';
import EmptyState from '../components/common/EmptyState';
import { getSeverityConfig } from '../utils/severity';

export default function ComparePage() {
  const [incidentId1, setIncidentId1] = useState('');
  const [incidentId2, setIncidentId2] = useState('');
  const [comparison, setComparison] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleCompare = async (e) => {
    e.preventDefault();
    if (!incidentId1.trim() || !incidentId2.trim()) return;

    setLoading(true);
    setError(null);
    setComparison(null);

    try {
      const response = await fetch(
        `${import.meta.env.VITE_API_BASE_URL}/api/incidents/compare`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            incident_id_1: incidentId1.trim(),
            incident_id_2: incidentId2.trim()
          })
        }
      );

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to compare incidents');
      }

      const data = await response.json();
      setComparison(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white flex items-center space-x-3">
            <GitCompare className="w-8 h-8 text-purple-400" />
            <span>Compare Incidents</span>
          </h1>
          <p className="text-gray-400 mt-1">
            Compare two incidents to find similarities and learn from patterns
          </p>
        </div>
      </div>

      {/* Explanation */}
      <div className="bg-gradient-to-r from-purple-500/10 to-pink-500/10 rounded-lg p-6 border border-purple-500/20">
        <div className="flex items-start space-x-4">
          <Brain className="w-8 h-8 text-purple-400 flex-shrink-0 mt-1" />
          <div>
            <h3 className="text-lg font-semibold text-white mb-2">
              Smart Comparison with Memory
            </h3>
            <p className="text-gray-300 leading-relaxed">
              The comparison engine uses Hindsight to analyze both incidents and identify:
              common patterns, similar root causes, shared symptoms, and lessons that apply to both cases.
            </p>
          </div>
        </div>
      </div>

      {/* Compare Form */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <form onSubmit={handleCompare} className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Incident 1 */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                First Incident ID
              </label>
              <input
                type="text"
                value={incidentId1}
                onChange={(e) => setIncidentId1(e.target.value)}
                placeholder="Enter first incident ID..."
                className="w-full px-4 py-3 bg-gray-900 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-purple-500"
              />
            </div>

            {/* Incident 2 */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Second Incident ID
              </label>
              <input
                type="text"
                value={incidentId2}
                onChange={(e) => setIncidentId2(e.target.value)}
                placeholder="Enter second incident ID..."
                className="w-full px-4 py-3 bg-gray-900 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-purple-500"
              />
            </div>
          </div>

          <div className="flex justify-center">
            <button
              type="submit"
              disabled={loading || !incidentId1.trim() || !incidentId2.trim()}
              className="px-8 py-3 bg-purple-500 text-white rounded-lg hover:bg-purple-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium flex items-center space-x-2"
            >
              {loading ? (
                <>
                  <LoadingSpinner size="small" />
                  <span>Comparing...</span>
                </>
              ) : (
                <>
                  <GitCompare className="w-5 h-5" />
                  <span>Compare Incidents</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>

      {error && <ErrorMessage message={error} />}

      {/* Results */}
      {!comparison && !loading && !error && (
        <EmptyState
          icon={GitCompare}
          message="No comparison yet"
          description="Enter two incident IDs above to compare them"
        />
      )}

      {comparison && (
        <div className="space-y-6">
          {/* Side-by-Side Comparison */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Incident 1 */}
            <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
              <h3 className="text-lg font-semibold text-white mb-4">
                Incident 1
              </h3>
              
              {comparison.incident1 && (
                <div className="space-y-3">
                  <div>
                    <div className="text-sm text-gray-400">ID</div>
                    <div className="text-white font-mono text-sm">
                      {comparison.incident1.id}
                    </div>
                  </div>

                  <div>
                    <div className="text-sm text-gray-400">Title</div>
                    <div className="text-white">
                      {comparison.incident1.title}
                    </div>
                  </div>

                  <div>
                    <div className="text-sm text-gray-400">Severity</div>
                    <span className={`inline-flex items-center px-2 py-1 rounded text-xs font-medium ${getSeverityConfig(comparison.incident1.severity).badge}`}>
                      {comparison.incident1.severity}
                    </span>
                  </div>

                  <div>
                    <div className="text-sm text-gray-400">Status</div>
                    <div className="text-white capitalize">
                      {comparison.incident1.status}
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Incident 2 */}
            <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
              <h3 className="text-lg font-semibold text-white mb-4">
                Incident 2
              </h3>
              
              {comparison.incident2 && (
                <div className="space-y-3">
                  <div>
                    <div className="text-sm text-gray-400">ID</div>
                    <div className="text-white font-mono text-sm">
                      {comparison.incident2.id}
                    </div>
                  </div>

                  <div>
                    <div className="text-sm text-gray-400">Title</div>
                    <div className="text-white">
                      {comparison.incident2.title}
                    </div>
                  </div>

                  <div>
                    <div className="text-sm text-gray-400">Severity</div>
                    <span className={`inline-flex items-center px-2 py-1 rounded text-xs font-medium ${getSeverityConfig(comparison.incident2.severity).badge}`}>
                      {comparison.incident2.severity}
                    </span>
                  </div>

                  <div>
                    <div className="text-sm text-gray-400">Status</div>
                    <div className="text-white capitalize">
                      {comparison.incident2.status}
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Similarities */}
          {comparison.similarities && comparison.similarities.length > 0 && (
            <div className="bg-gray-800 rounded-lg p-6 border border-green-500/30">
              <h3 className="text-lg font-semibold text-white mb-4 flex items-center space-x-2">
                <ArrowRight className="w-5 h-5 text-green-400" />
                <span>Similarities Found</span>
              </h3>
              
              <ul className="space-y-2">
                {comparison.similarities.map((similarity, index) => (
                  <li key={index} className="flex items-start space-x-3">
                    <span className="text-green-400 mt-1">✓</span>
                    <span className="text-gray-300">{similarity}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Differences */}
          {comparison.differences && comparison.differences.length > 0 && (
            <div className="bg-gray-800 rounded-lg p-6 border border-orange-500/30">
              <h3 className="text-lg font-semibold text-white mb-4 flex items-center space-x-2">
                <AlertCircle className="w-5 h-5 text-orange-400" />
                <span>Key Differences</span>
              </h3>
              
              <ul className="space-y-2">
                {comparison.differences.map((difference, index) => (
                  <li key={index} className="flex items-start space-x-3">
                    <span className="text-orange-400 mt-1">•</span>
                    <span className="text-gray-300">{difference}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Analysis */}
          {comparison.analysis && (
            <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
              <h3 className="text-lg font-semibold text-white mb-4 flex items-center space-x-2">
                <Brain className="w-5 h-5 text-purple-400" />
                <span>AI Analysis</span>
              </h3>
              
              <div className="text-gray-300 leading-relaxed whitespace-pre-wrap">
                {comparison.analysis}
              </div>
            </div>
          )}

          {/* Recommendations */}
          {comparison.recommendations && comparison.recommendations.length > 0 && (
            <div className="bg-cyan-500/10 rounded-lg p-6 border border-cyan-500/30">
              <h3 className="text-lg font-semibold text-white mb-4">
                Recommendations
              </h3>
              
              <ul className="space-y-2">
                {comparison.recommendations.map((rec, index) => (
                  <li key={index} className="flex items-start space-x-3">
                    <span className="text-cyan-400 mt-1">→</span>
                    <span className="text-gray-300">{rec}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
