import { useState } from 'react';
import { Lightbulb, Brain, Search, TrendingUp, Target } from 'lucide-react';
import LoadingSpinner from '../components/common/LoadingSpinner';
import ErrorMessage from '../components/common/ErrorMessage';
import EmptyState from '../components/common/EmptyState';

export default function LearningCenter() {
  const [query, setQuery] = useState('');
  const [insights, setInsights] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleReflect = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(
        `${import.meta.env.VITE_API_BASE_URL}/api/memory/reflect`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ topic: query })
        }
      );

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to generate insights');
      }

      const data = await response.json();
      setInsights(data.insights || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const exampleTopics = [
    'database performance',
    'API reliability',
    'authentication patterns',
    'memory optimization',
    'incident prevention'
  ];

  const handleExampleTopic = (topic) => {
    setQuery(topic);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white flex items-center space-x-3">
            <Lightbulb className="w-8 h-8 text-yellow-400" />
            <span>Learning Center</span>
          </h1>
          <p className="text-gray-400 mt-1">
            Generate insights and patterns from historical incident data
          </p>
        </div>
      </div>

      {/* Explanation Card */}
      <div className="bg-gradient-to-r from-yellow-500/10 to-orange-500/10 rounded-lg p-6 border border-yellow-500/20">
        <div className="flex items-start space-x-4">
          <Brain className="w-8 h-8 text-yellow-400 flex-shrink-0 mt-1" />
          <div>
            <h3 className="text-lg font-semibold text-white mb-2">
              How Learning Works
            </h3>
            <p className="text-gray-300 leading-relaxed">
              The Learning Center uses <span className="text-cyan-400 font-medium">Hindsight's REFLECT</span> capability
              to analyze patterns across all stored incident memories. Ask about a topic, and the agent will:
            </p>
            <ul className="mt-3 space-y-2 text-gray-300">
              <li className="flex items-start space-x-2">
                <span className="text-cyan-400">•</span>
                <span>Search all relevant historical incidents</span>
              </li>
              <li className="flex items-start space-x-2">
                <span className="text-cyan-400">•</span>
                <span>Identify common patterns and trends</span>
              </li>
              <li className="flex items-start space-x-2">
                <span className="text-cyan-400">•</span>
                <span>Generate actionable insights and recommendations</span>
              </li>
            </ul>
          </div>
        </div>
      </div>

      {/* Reflect Form */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <form onSubmit={handleReflect} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              What topic would you like to learn about?
            </label>
            <div className="relative">
              <Brain className="absolute left-4 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Enter a topic to reflect on... (e.g., 'database performance')"
                className="w-full pl-12 pr-4 py-3 bg-gray-900 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500"
              />
            </div>
          </div>

          <div className="flex items-center justify-between">
            <div className="flex flex-wrap gap-2">
              <span className="text-sm text-gray-400 mr-2">Examples:</span>
              {exampleTopics.map((topic) => (
                <button
                  key={topic}
                  type="button"
                  onClick={() => handleExampleTopic(topic)}
                  className="px-3 py-1 bg-gray-900 text-gray-300 text-sm rounded-lg hover:bg-gray-700 transition-colors"
                >
                  {topic}
                </button>
              ))}
            </div>

            <button
              type="submit"
              disabled={loading || !query.trim()}
              className="px-6 py-2 bg-yellow-500 text-gray-900 rounded-lg hover:bg-yellow-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium flex items-center space-x-2"
            >
              {loading ? (
                <>
                  <LoadingSpinner size="small" />
                  <span>Reflecting...</span>
                </>
              ) : (
                <>
                  <Lightbulb className="w-5 h-5" />
                  <span>Generate Insights</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>

      {error && <ErrorMessage message={error} />}

      {/* Results */}
      {insights.length === 0 && !loading && !error && (
        <EmptyState
          icon={Lightbulb}
          message="No insights yet"
          description="Enter a topic above to generate insights from historical incidents"
        />
      )}

      {insights.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold text-white">
              Generated {insights.length} {insights.length === 1 ? 'Insight' : 'Insights'}
            </h2>
          </div>

          <div className="grid grid-cols-1 gap-4">
            {insights.map((insight, index) => (
              <div
                key={index}
                className="bg-gray-800 rounded-lg p-6 border border-gray-700 hover:border-yellow-500/30 transition-all"
              >
                <div className="flex items-start space-x-4">
                  <div className="flex-shrink-0 w-10 h-10 bg-yellow-500/20 rounded-lg flex items-center justify-center">
                    <Lightbulb className="w-6 h-6 text-yellow-400" />
                  </div>
                  
                  <div className="flex-1">
                    <div className="flex items-center justify-between mb-3">
                      <h3 className="text-lg font-semibold text-white">
                        Insight #{index + 1}
                      </h3>
                      <span className="px-3 py-1 bg-yellow-500/20 text-yellow-400 text-xs rounded-lg border border-yellow-500/30">
                        AI Generated
                      </span>
                    </div>

                    <div className="text-gray-300 leading-relaxed whitespace-pre-wrap">
                      {insight}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Action Card */}
          <div className="bg-cyan-500/10 rounded-lg p-5 border border-cyan-500/20">
            <div className="flex items-start space-x-3">
              <Target className="w-6 h-6 text-cyan-400 flex-shrink-0 mt-1" />
              <div>
                <h4 className="text-white font-medium mb-2">
                  Next Steps
                </h4>
                <p className="text-gray-300 text-sm">
                  These insights are generated from real incident history. Consider incorporating
                  them into your runbooks, monitoring alerts, and incident response procedures.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Statistics Section */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center space-x-2">
          <TrendingUp className="w-5 h-5 text-green-400" />
          <span>Learning Progress</span>
        </h3>
        
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-gray-900 rounded-lg p-4">
            <div className="text-gray-400 text-sm mb-1">Insights Generated</div>
            <div className="text-2xl font-bold text-white">{insights.length}</div>
          </div>
          
          <div className="bg-gray-900 rounded-lg p-4">
            <div className="text-gray-400 text-sm mb-1">Topic Analyzed</div>
            <div className="text-lg font-medium text-white truncate">
              {query || 'None yet'}
            </div>
          </div>
          
          <div className="bg-gray-900 rounded-lg p-4">
            <div className="text-gray-400 text-sm mb-1">Status</div>
            <div className="text-lg font-medium text-green-400">
              {loading ? 'Processing...' : insights.length > 0 ? 'Complete' : 'Ready'}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
