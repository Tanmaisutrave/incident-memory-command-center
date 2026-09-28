import { useState, useEffect } from 'react';
import { Brain, Search, Calendar, Tag, TrendingUp, Filter } from 'lucide-react';
import LoadingSpinner from '../components/common/LoadingSpinner';
import ErrorMessage from '../components/common/ErrorMessage';
import EmptyState from '../components/common/EmptyState';
import { formatTimestamp } from '../utils/formatters';

export default function MemoryExplorer() {
  const [query, setQuery] = useState('');
  const [memories, setMemories] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedTags, setSelectedTags] = useState([]);

  // Load stats on mount
  useEffect(() => {
    loadStats();
  }, []);

  const loadStats = async () => {
    try {
      const response = await fetch(`${import.meta.env.VITE_API_BASE_URL}/api/memory/stats`);
      if (!response.ok) throw new Error('Failed to load memory stats');
      const data = await response.json();
      setStats(data);
    } catch (err) {
      console.error('Stats error:', err);
    }
  };

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(
        `${import.meta.env.VITE_API_BASE_URL}/api/memory/recall`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query, limit: 20 })
        }
      );

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to recall memories');
      }

      const data = await response.json();
      
      // Map backend response to frontend format
      const mappedMemories = (data.memories || []).map(memory => ({
        memory_text: memory.memory_text || '',
        memory_type: memory.memory_type || '',
        relevance_score: memory.relevance_score || null,
        // For compatibility, also map to expected field names
        content: memory.memory_text || '',
        metadata: {
          memory_type: memory.memory_type || '',
          tags: [] // Tags not available in current backend response
        },
        similarity_score: memory.relevance_score || null
      }));
      
      setMemories(mappedMemories);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const exampleQueries = [
    'database connection issues',
    'API rate limiting',
    'high memory usage',
    'authentication failures',
    'slow queries'
  ];

  const handleExampleQuery = (exampleQuery) => {
    setQuery(exampleQuery);
  };

  const toggleTag = (tag) => {
    setSelectedTags(prev =>
      prev.includes(tag)
        ? prev.filter(t => t !== tag)
        : [...prev, tag]
    );
  };

  const filteredMemories = selectedTags.length === 0
    ? memories
    : memories.filter(memory => {
        const memoryType = memory.memory_type || memory.metadata?.memory_type || '';
        return selectedTags.includes(memoryType);
      });

  // Extract unique memory types as "tags"
  const allTags = [...new Set(
    memories.map(m => m.memory_type || m.metadata?.memory_type).filter(Boolean)
  )].sort();

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white flex items-center space-x-3">
            <Brain className="w-8 h-8 text-cyan-400" />
            <span>Memory Explorer</span>
          </h1>
          <p className="text-gray-400 mt-1">
            Search through past incident learnings and patterns
          </p>
        </div>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-gray-400 text-sm">Total Memories</div>
                <div className="text-2xl font-bold text-white mt-1">
                  {stats.total_memories}
                </div>
              </div>
              <Brain className="w-8 h-8 text-cyan-400" />
            </div>
          </div>

          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-gray-400 text-sm">Memory Bank</div>
                <div className="text-xl font-bold text-white mt-1">
                  {stats.memory_bank}
                </div>
              </div>
              <Tag className="w-8 h-8 text-purple-400" />
            </div>
          </div>

          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-gray-400 text-sm">Learning Rate</div>
                <div className="text-2xl font-bold text-white mt-1">High</div>
              </div>
              <TrendingUp className="w-8 h-8 text-green-400" />
            </div>
          </div>
        </div>
      )}

      {/* Search Section */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <form onSubmit={handleSearch} className="space-y-4">
          <div className="relative">
            <Search className="absolute left-4 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search memories... (e.g., 'database issues', 'API failures')"
              className="w-full pl-12 pr-4 py-3 bg-gray-900 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500"
            />
          </div>

          <div className="flex items-center justify-between">
            <div className="flex flex-wrap gap-2">
              {exampleQueries.map((exampleQuery) => (
                <button
                  key={exampleQuery}
                  type="button"
                  onClick={() => handleExampleQuery(exampleQuery)}
                  className="px-3 py-1 bg-gray-900 text-gray-300 text-sm rounded-lg hover:bg-gray-700 transition-colors"
                >
                  {exampleQuery}
                </button>
              ))}
            </div>

            <button
              type="submit"
              disabled={loading || !query.trim()}
              className="px-6 py-2 bg-cyan-500 text-white rounded-lg hover:bg-cyan-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium flex items-center space-x-2"
            >
              {loading ? (
                <>
                  <LoadingSpinner size="small" />
                  <span>Searching...</span>
                </>
              ) : (
                <>
                  <Search className="w-5 h-5" />
                  <span>Search Memories</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>

      {error && <ErrorMessage message={error} />}

      {/* Tag Filter */}
      {allTags.length > 0 && (
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <div className="flex items-center space-x-2 mb-3">
            <Filter className="w-5 h-5 text-gray-400" />
            <span className="text-sm font-medium text-gray-300">Filter by Tags:</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {allTags.map((tag) => (
              <button
                key={tag}
                onClick={() => toggleTag(tag)}
                className={`
                  px-3 py-1 rounded-lg text-sm font-medium transition-all
                  ${selectedTags.includes(tag)
                    ? 'bg-cyan-500 text-white'
                    : 'bg-gray-900 text-gray-400 hover:bg-gray-700'
                  }
                `}
              >
                {tag}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Results */}
      {memories.length === 0 && !loading && !error && (
        <EmptyState
          icon={Brain}
          message="Search for incident memories to explore past learnings"
          description="Use the search bar above to find relevant incident memories"
        />
      )}

      {filteredMemories.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold text-white">
              Found {filteredMemories.length} {filteredMemories.length === 1 ? 'Memory' : 'Memories'}
            </h2>
          </div>

          <div className="space-y-3">
            {filteredMemories.map((memory, index) => (
              <div
                key={memory.id || index}
                className="bg-gray-800 rounded-lg p-5 border border-gray-700 hover:border-gray-600 transition-colors"
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex-1">
                    {/* Memory Text Content */}
                    <div className="text-white font-medium mb-2">
                      {memory.content || memory.memory_text || 'No content available'}
                    </div>
                    
                    {/* Memory Type Badge */}
                    {memory.memory_type && (
                      <div className="mb-2">
                        <span className="px-2 py-1 bg-purple-500/20 text-purple-400 text-xs rounded-lg border border-purple-500/30">
                          {memory.memory_type}
                        </span>
                      </div>
                    )}
                    
                    {/* Metadata if available */}
                    {memory.metadata && (
                      <div className="space-y-2">
                        {memory.metadata.tags && memory.metadata.tags.length > 0 && (
                          <div className="flex flex-wrap gap-2">
                            {memory.metadata.tags.map((tag, idx) => (
                              <span
                                key={idx}
                                className="px-2 py-1 bg-gray-900 text-cyan-400 text-xs rounded-lg border border-cyan-500/30"
                              >
                                <Tag className="w-3 h-3 inline mr-1" />
                                {tag}
                              </span>
                            ))}
                          </div>
                        )}

                        <div className="flex items-center space-x-4 text-xs text-gray-500">
                          {memory.metadata.timestamp && (
                            <div className="flex items-center space-x-1">
                              <Calendar className="w-3 h-3" />
                              <span>{formatTimestamp(memory.metadata.timestamp)}</span>
                            </div>
                          )}
                          
                          {memory.metadata.incident_id && (
                            <div>
                              Incident: {memory.metadata.incident_id.substring(0, 8)}
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Relevance Score */}
                  {(memory.similarity_score || memory.relevance_score) && (
                    <div className="ml-4 text-right">
                      <div className="text-xs text-gray-500">Relevance</div>
                      <div className="text-lg font-bold text-cyan-400">
                        {Math.round((memory.similarity_score || memory.relevance_score || 0) * 100)}%
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
