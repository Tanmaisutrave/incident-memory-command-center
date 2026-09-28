import { useState } from 'react';
import { AlertCircle, Brain, Sparkles, CheckCircle2 } from 'lucide-react';
import LoadingSpinner from '../components/common/LoadingSpinner';
import ErrorMessage from '../components/common/ErrorMessage';
import { api, APIError } from '../services/api';
import AnalysisResult from '../components/analysis/AnalysisResult';

const DEMO_INCIDENTS = [
  {
    title: 'Payment API Redis Timeout - High Latency',
    service: 'payment-api',
    environment: 'production',
    severity: 'P1',
    symptoms: 'API response time increased to 7.5 seconds, Redis timeout errors in logs, 502 bad gateway responses, error rate 18%',
    error_logs: 'RedisTimeoutError: Timeout connecting to Redis after 5000ms. Connection pool saturated.',
    metrics: { latency_p99: 7500, error_rate: 0.18, active_connections: 250 },
    suspected_causes: ['Redis connection pool exhaustion', 'Network latency'],
    tags: ['redis', 'timeout', 'performance'],
  },
  {
    title: 'Order Service Database Connection Timeout',
    service: 'order-service',
    environment: 'production',
    severity: 'P1',
    symptoms: 'Database queries timing out, connection acquisition taking 20+ seconds, 500 errors',
    error_logs: 'PSQLException: Connection is not available, request timed out after 30000ms',
    suspected_causes: ['Database connection pool exhaustion'],
    tags: ['database', 'postgres', 'timeout'],
  },
];

export default function AnalyzeIncident() {
  const [formData, setFormData] = useState({
    title: '',
    service: '',
    environment: 'production',
    severity: 'P2',
    symptoms: '',
    error_logs: '',
    metrics: '',
    suspected_causes: '',
    tags: '',
  });

  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [analysisStage, setAnalysisStage] = useState('');

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const loadDemo = (demoIncident) => {
    setFormData({
      title: demoIncident.title,
      service: demoIncident.service,
      environment: demoIncident.environment,
      severity: demoIncident.severity,
      symptoms: demoIncident.symptoms,
      error_logs: demoIncident.error_logs || '',
      metrics: demoIncident.metrics ? JSON.stringify(demoIncident.metrics, null, 2) : '',
      suspected_causes: demoIncident.suspected_causes?.join(', ') || '',
      tags: demoIncident.tags?.join(', ') || '',
    });
    setAnalysis(null);
    setError(null);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setAnalysis(null);

    try {
      // Stage 1: Analyzing
      setAnalysisStage('Analyzing incident details...');
      await new Promise(resolve => setTimeout(resolve, 500));

      // Stage 2: Searching memory
      setAnalysisStage('Searching Hindsight memory for similar incidents...');
      await new Promise(resolve => setTimeout(resolve, 500));

      // Prepare request data
      const incidentData = {
        title: formData.title,
        service: formData.service,
        environment: formData.environment,
        severity: formData.severity,
        symptoms: formData.symptoms,
        ...(formData.error_logs && { error_logs: formData.error_logs }),
        ...(formData.metrics && {
          metrics: JSON.parse(formData.metrics)
        }),
        ...(formData.suspected_causes && {
          suspected_causes: formData.suspected_causes.split(',').map(s => s.trim()).filter(Boolean)
        }),
        ...(formData.tags && {
          tags: formData.tags.split(',').map(s => s.trim()).filter(Boolean)
        }),
      };

      // Stage 3: AI Analysis
      setAnalysisStage('Generating AI-powered diagnosis...');
      
      const result = await api.analyzeIncident(incidentData);
      
      setAnalysisStage('');
      setAnalysis(result);
    } catch (err) {
      setError(err instanceof APIError ? err.message : 'Failed to analyze incident');
      setAnalysisStage('');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-8">
      <div className="max-w-6xl mx-auto space-y-8">
        {/* Header */}
        <div>
          <h2 className="text-3xl font-bold text-white mb-2">Analyze Incident</h2>
          <p className="text-slate-400">
            Get AI-powered analysis with historical context from Hindsight memory
          </p>
        </div>

        {/* Demo Buttons */}
        <div className="flex gap-3">
          {DEMO_INCIDENTS.map((demo, idx) => (
            <button
              key={idx}
              onClick={() => loadDemo(demo)}
              className="px-4 py-2 bg-purple-900/50 hover:bg-purple-800/50 border border-purple-700 text-purple-300 rounded-lg text-sm font-medium transition-colors"
            >
              Load Demo {idx + 1}
            </button>
          ))}
        </div>

        {error && <ErrorMessage error={error} onRetry={() => setError(null)} />}

        {/* Form */}
        <form onSubmit={handleSubmit} className="bg-surface border border-border rounded-lg p-6 space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Title */}
            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Incident Title *
              </label>
              <input
                type="text"
                name="title"
                value={formData.title}
                onChange={handleChange}
                required
                className="w-full px-4 py-2 bg-background border border-border rounded-lg text-white focus:border-primary focus:ring-1 focus:ring-primary"
                placeholder="e.g., Payment API High Latency"
              />
            </div>

            {/* Service */}
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Service *
              </label>
              <input
                type="text"
                name="service"
                value={formData.service}
                onChange={handleChange}
                required
                className="w-full px-4 py-2 bg-background border border-border rounded-lg text-white focus:border-primary focus:ring-1 focus:ring-primary"
                placeholder="e.g., payment-api"
              />
            </div>

            {/* Environment */}
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Environment *
              </label>
              <select
                name="environment"
                value={formData.environment}
                onChange={handleChange}
                required
                className="w-full px-4 py-2 bg-background border border-border rounded-lg text-white focus:border-primary focus:ring-1 focus:ring-primary"
              >
                <option value="production">Production</option>
                <option value="staging">Staging</option>
                <option value="development">Development</option>
              </select>
            </div>

            {/* Severity */}
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Severity *
              </label>
              <select
                name="severity"
                value={formData.severity}
                onChange={handleChange}
                required
                className="w-full px-4 py-2 bg-background border border-border rounded-lg text-white focus:border-primary focus:ring-1 focus:ring-primary"
              >
                <option value="P1">P1 - Critical</option>
                <option value="P2">P2 - High</option>
                <option value="P3">P3 - Medium</option>
                <option value="P4">P4 - Low</option>
              </select>
            </div>

            {/* Tags */}
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Tags
              </label>
              <input
                type="text"
                name="tags"
                value={formData.tags}
                onChange={handleChange}
                className="w-full px-4 py-2 bg-background border border-border rounded-lg text-white focus:border-primary focus:ring-1 focus:ring-primary"
                placeholder="e.g., redis, performance, timeout"
              />
            </div>

            {/* Symptoms */}
            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Symptoms *
              </label>
              <textarea
                name="symptoms"
                value={formData.symptoms}
                onChange={handleChange}
                required
                rows="3"
                className="w-full px-4 py-2 bg-background border border-border rounded-lg text-white focus:border-primary focus:ring-1 focus:ring-primary font-mono text-sm"
                placeholder="Describe the symptoms you're observing..."
              />
            </div>

            {/* Error Logs */}
            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Error Logs
              </label>
              <textarea
                name="error_logs"
                value={formData.error_logs}
                onChange={handleChange}
                rows="4"
                className="w-full px-4 py-2 bg-background border border-border rounded-lg text-white focus:border-primary focus:ring-1 focus:ring-primary font-mono text-sm"
                placeholder="Paste relevant error logs..."
              />
            </div>

            {/* Metrics */}
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Metrics (JSON)
              </label>
              <textarea
                name="metrics"
                value={formData.metrics}
                onChange={handleChange}
                rows="4"
                className="w-full px-4 py-2 bg-background border border-border rounded-lg text-white focus:border-primary focus:ring-1 focus:ring-primary font-mono text-sm"
                placeholder='{"latency_p99": 8200, "error_rate": 0.23}'
              />
            </div>

            {/* Suspected Causes */}
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Suspected Causes
              </label>
              <textarea
                name="suspected_causes"
                value={formData.suspected_causes}
                onChange={handleChange}
                rows="4"
                className="w-full px-4 py-2 bg-background border border-border rounded-lg text-white focus:border-primary focus:ring-1 focus:ring-primary"
                placeholder="List suspected causes, separated by commas"
              />
            </div>
          </div>

          {/* Submit Button */}
          <div className="flex justify-end">
            <button
              type="submit"
              disabled={loading}
              className="inline-flex items-center gap-2 px-6 py-3 bg-primary hover:bg-primary-hover text-white rounded-lg font-semibold transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? (
                <>
                  <LoadingSpinner size="sm" />
                  Analyzing...
                </>
              ) : (
                <>
                  <Sparkles className="w-5 h-5" />
                  Analyze with Hindsight
                </>
              )}
            </button>
          </div>
        </form>

        {/* Loading State */}
        {loading && analysisStage && (
          <div className="bg-surface border border-primary/50 rounded-lg p-6">
            <div className="flex items-center gap-4">
              <LoadingSpinner size="md" />
              <div>
                <h3 className="text-lg font-semibold text-white mb-1">Analyzing Incident</h3>
                <p className="text-sm text-slate-400">{analysisStage}</p>
              </div>
            </div>
          </div>
        )}

        {/* Analysis Result */}
        {analysis && <AnalysisResult analysis={analysis} />}
      </div>
    </div>
  );
}
