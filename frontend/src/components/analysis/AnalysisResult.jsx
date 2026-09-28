import { useState } from 'react';
import {
  Brain,
  Target,
  CheckCircle2,
  AlertTriangle,
  Lightbulb,
  History,
  TrendingUp,
  FileText
} from 'lucide-react';
import { formatPercentage, formatTimestamp } from '../../utils/formatters';
import { getSeverityBadgeClass } from '../../utils/severity';
import ResolutionForm from './ResolutionForm';

export default function AnalysisResult({ analysis }) {
  const [showResolutionForm, setShowResolutionForm] = useState(false);

  return (
    <div className="space-y-6">
      {/* Summary Card */}
      <div className="bg-surface border border-border rounded-lg p-6">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h3 className="text-2xl font-bold text-white mb-2">Incident Analysis</h3>
            <p className="text-sm text-slate-400">
              Generated at {formatTimestamp(analysis.analysis_timestamp)}
            </p>
          </div>
          <span className={getSeverityBadgeClass(analysis.severity_assessment)}>
            {analysis.severity_assessment}
          </span>
        </div>

        <div className="prose prose-invert max-w-none">
          <p className="text-slate-300">{analysis.summary}</p>
        </div>
      </div>

      {/* Root Cause & Confidence */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-surface border border-border rounded-lg p-6">
          <div className="flex items-center gap-3 mb-4">
            <Target className="w-6 h-6 text-red-400" />
            <h4 className="text-lg font-semibold text-white">Likely Root Cause</h4>
          </div>
          <p className="text-slate-300">{analysis.likely_root_cause}</p>
        </div>

        <div className="bg-surface border border-border rounded-lg p-6">
          <div className="flex items-center gap-3 mb-4">
            <TrendingUp className="w-6 h-6 text-primary" />
            <h4 className="text-lg font-semibold text-white">Confidence</h4>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex-1">
              <div className="w-full bg-slate-800 rounded-full h-3">
                <div
                  className="bg-primary h-3 rounded-full transition-all"
                  style={{ width: `${analysis.confidence * 100}%` }}
                />
              </div>
            </div>
            <span className="text-2xl font-bold text-primary">
              {formatPercentage(analysis.confidence)}
            </span>
          </div>
          <p className="text-sm text-slate-400 mt-2">
            Based on {analysis.used_memory ? 'historical evidence and' : ''} current symptoms
          </p>
        </div>
      </div>

      {/* Historical Memory - THE MOST IMPORTANT SECTION */}
      {analysis.used_memory && analysis.historical_incidents && analysis.historical_incidents.length > 0 && (
        <div className="bg-gradient-to-br from-primary/10 to-purple-500/10 border-2 border-primary/50 rounded-lg p-6 shadow-xl">
          <div className="flex items-start justify-between mb-6">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 bg-primary/20 rounded-xl flex items-center justify-center">
                <Brain className="w-7 h-7 text-primary animate-pulse" />
              </div>
              <div>
                <h3 className="text-2xl font-bold text-white flex items-center gap-2">
                  🧠 HINDSIGHT MEMORY
                  <span className="text-sm font-normal text-primary">RECALL</span>
                </h3>
                <p className="text-sm text-primary mt-1">
                  {analysis.historical_incidents.length} related {analysis.historical_incidents.length === 1 ? 'incident' : 'incidents'} found in historical data
                </p>
              </div>
            </div>
            <div className="text-right">
              <div className="text-3xl font-bold text-primary">
                {analysis.historical_incidents.length}
              </div>
              <div className="text-xs text-slate-400">matches</div>
            </div>
          </div>

          {/* Why This Matters Callout */}
          <div className="bg-cyan-500/10 border border-cyan-500/30 rounded-lg p-4 mb-6">
            <div className="flex items-start gap-3">
              <Lightbulb className="w-5 h-5 text-cyan-400 flex-shrink-0 mt-0.5" />
              <div>
                <h4 className="text-sm font-semibold text-cyan-400 mb-1">Why This Matters</h4>
                <p className="text-sm text-slate-300">
                  The agent found {analysis.historical_incidents.length} similar historical {analysis.historical_incidents.length === 1 ? 'incident' : 'incidents'} with 
                  matching symptoms. These past resolutions inform the current recommendations with 
                  <strong className="text-cyan-400"> evidence-based insights</strong> instead of generic troubleshooting.
                </p>
              </div>
            </div>
          </div>

          {/* Historical Incidents */}
          <div className="space-y-4">
            <h4 className="text-sm font-semibold text-white uppercase tracking-wide">Related Past Incidents</h4>
            {analysis.historical_incidents.slice(0, 3).map((incident, idx) => (
              <HistoricalIncidentCard key={idx} incident={incident} index={idx + 1} />
            ))}
          </div>

          {analysis.historical_incidents.length > 3 && (
            <div className="mt-4 text-center">
              <span className="text-sm text-slate-400">
                +{analysis.historical_incidents.length - 3} more {analysis.historical_incidents.length - 3 === 1 ? 'incident' : 'incidents'} in memory
              </span>
            </div>
          )}

          {analysis.historical_evidence && analysis.historical_evidence.length > 0 && (
            <div className="mt-6 pt-6 border-t border-primary/30">
              <h4 className="text-sm font-semibold text-primary mb-3 uppercase tracking-wide">Historical Evidence Used</h4>
              <ul className="space-y-2">
                {analysis.historical_evidence.map((evidence, idx) => (
                  <li key={idx} className="flex items-start gap-2 text-sm text-slate-300">
                    <History className="w-4 h-4 text-primary mt-0.5 flex-shrink-0" />
                    <span>{evidence}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {analysis.memory_insights && analysis.memory_insights.length > 0 && (
            <div className="mt-4 pt-4 border-t border-primary/30">
              <h4 className="text-sm font-semibold text-yellow-400 mb-3 uppercase tracking-wide">Memory-Informed Insights</h4>
              <ul className="space-y-2">
                {analysis.memory_insights.map((insight, idx) => (
                  <li key={idx} className="flex items-start gap-2 text-sm text-slate-300">
                    <Lightbulb className="w-4 h-4 text-yellow-400 mt-0.5 flex-shrink-0" />
                    <span>{insight}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* No Memory Used - Show What's Different */}
      {!analysis.used_memory && (
        <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-6">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-6 h-6 text-yellow-400 flex-shrink-0" />
            <div>
              <h4 className="text-lg font-semibold text-white mb-2">Generic Analysis</h4>
              <p className="text-sm text-slate-300 mb-3">
                This analysis was performed without historical memory context. The recommendations 
                are based on general best practices rather than your organization's specific experience.
              </p>
              <p className="text-xs text-slate-400 italic">
                💡 Tip: Resolve and remember this incident to improve future recommendations
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Why This Recommendation */}
      {analysis.historical_evidence && analysis.historical_evidence.length > 0 && (
        <div className="bg-surface-secondary border border-primary/30 rounded-lg p-6">
          <h4 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <FileText className="w-5 h-5 text-primary" />
            Why This Recommendation?
          </h4>
          <div className="space-y-4">
            <div>
              <h5 className="text-sm font-semibold text-slate-400 mb-2">Current Evidence:</h5>
              <p className="text-sm text-slate-300">{analysis.summary}</p>
            </div>
            <div>
              <h5 className="text-sm font-semibold text-slate-400 mb-2">Historical Pattern:</h5>
              <p className="text-sm text-slate-300">
                {analysis.historical_evidence[0]}
              </p>
            </div>
            <div>
              <h5 className="text-sm font-semibold text-slate-400 mb-2">Current Recommendation:</h5>
              <p className="text-sm text-slate-300">{analysis.next_steps}</p>
            </div>
          </div>
        </div>
      )}

      {/* Recommended Actions */}
      {analysis.recommended_actions && analysis.recommended_actions.length > 0 && (
        <div className="bg-surface border border-border rounded-lg p-6">
          <div className="flex items-center gap-3 mb-4">
            <CheckCircle2 className="w-6 h-6 text-green-400" />
            <h4 className="text-lg font-semibold text-white">Recommended Actions</h4>
          </div>
          <ol className="space-y-3">
            {analysis.recommended_actions.map((action, idx) => (
              <li key={idx} className="flex gap-4">
                <span className="flex-shrink-0 w-8 h-8 bg-primary/20 text-primary rounded-lg flex items-center justify-center font-semibold text-sm">
                  {idx + 1}
                </span>
                <p className="text-slate-300 pt-1">{action}</p>
              </li>
            ))}
          </ol>
        </div>
      )}

      {/* Investigation Steps */}
      {analysis.investigation_steps && analysis.investigation_steps.length > 0 && (
        <div className="bg-surface border border-border rounded-lg p-6">
          <div className="flex items-center gap-3 mb-4">
            <Lightbulb className="w-6 h-6 text-yellow-400" />
            <h4 className="text-lg font-semibold text-white">Investigation Steps</h4>
          </div>
          <ul className="space-y-2">
            {analysis.investigation_steps.map((step, idx) => (
              <li key={idx} className="flex items-start gap-3 text-slate-300">
                <input type="checkbox" className="mt-1" />
                <span>{step}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Risk Notes */}
      {analysis.risk_notes && (
        <div className="bg-yellow-950/30 border border-yellow-800/50 rounded-lg p-6">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-6 h-6 text-yellow-400 flex-shrink-0" />
            <div>
              <h4 className="text-lg font-semibold text-yellow-400 mb-2">Risk Notes</h4>
              <p className="text-slate-300">{analysis.risk_notes}</p>
            </div>
          </div>
        </div>
      )}

      {/* Resolve Button */}
      <div className="flex justify-end">
        <button
          onClick={() => setShowResolutionForm(!showResolutionForm)}
          className="px-6 py-3 bg-green-600 hover:bg-green-700 text-white rounded-lg font-semibold transition-colors"
        >
          {showResolutionForm ? 'Cancel Resolution' : 'Resolve & Remember'}
        </button>
      </div>

      {/* Resolution Form */}
      {showResolutionForm && (
        <ResolutionForm
          incidentId={analysis.incident_id}
          onSuccess={() => setShowResolutionForm(false)}
          onCancel={() => setShowResolutionForm(false)}
        />
      )}
    </div>
  );
}

function HistoricalIncidentCard({ incident, index }) {
  const [expanded, setExpanded] = useState(false);
  
  // Enhanced parsing of memory text
  const text = incident.memory_text || '';
  
  // Extract structured information
  const incidentIdMatch = text.match(/(?:INCIDENT|Incident):\s*(\S+)/i) || text.match(/INC-\d+/);
  const incidentId = incidentIdMatch ? incidentIdMatch[1] || incidentIdMatch[0] : null;
  
  const rootCauseMatch = text.match(/(?:Root cause|caused by):\s*([^|.\n]+)/i);
  const rootCause = rootCauseMatch ? rootCauseMatch[1].trim() : null;
  
  const resolutionMatch = text.match(/(?:Resolution|Resolved by|Fixed by):\s*([^|.\n]+)/i);
  const resolution = resolutionMatch ? resolutionMatch[1].trim() : null;
  
  const outcomeMatch = text.match(/(?:Outcome|Result):\s*([^|.\n]+)/i);
  const outcome = outcomeMatch ? outcomeMatch[1].trim() : null;
  
  const timestampMatch = text.match(/(?:When|Date|Time):\s*([^|.\n]+)/i);
  const timestamp = timestampMatch ? timestampMatch[1].trim() : null;
  
  return (
    <div className="bg-surface/80 border border-primary/30 rounded-lg p-4 hover:border-primary/50 transition-colors relative">
      {/* Index badge */}
      {index && (
        <div className="absolute -top-2 -left-2 w-6 h-6 bg-primary rounded-full flex items-center justify-center text-xs font-bold text-white shadow-lg">
          {index}
        </div>
      )}
      
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 bg-primary rounded-full animate-pulse" />
          {incidentId ? (
            <span className="font-mono text-sm font-semibold text-primary">{incidentId}</span>
          ) : (
            <span className="text-sm font-semibold text-primary">Historical Incident</span>
          )}
          {timestamp && (
            <span className="text-xs text-slate-500">{timestamp}</span>
          )}
        </div>
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-xs text-primary hover:text-cyan-300 transition-colors"
        >
          {expanded ? 'Less' : 'More'}
        </button>
      </div>
      
      {/* Structured information when available */}
      {!expanded && (rootCause || resolution) && (
        <div className="space-y-2 mb-2">
          {rootCause && (
            <div>
              <span className="text-xs font-semibold text-slate-400">Root Cause: </span>
              <span className="text-sm text-slate-300">{rootCause}</span>
            </div>
          )}
          {resolution && (
            <div>
              <span className="text-xs font-semibold text-green-400">Resolution: </span>
              <span className="text-sm text-slate-300">{resolution}</span>
            </div>
          )}
          {outcome && (
            <div>
              <span className="text-xs font-semibold text-cyan-400">Outcome: </span>
              <span className="text-sm text-slate-300">{outcome}</span>
            </div>
          )}
        </div>
      )}
      
      {/* Full text when expanded */}
      {expanded && (
        <div className="mt-3 pt-3 border-t border-primary/20">
          <p className="text-sm text-slate-300 leading-relaxed whitespace-pre-wrap">
            {text}
          </p>
        </div>
      )}
      
      {/* Preview when not expanded and no structured data */}
      {!expanded && !rootCause && !resolution && (
        <p className="text-sm text-slate-300">
          {text.substring(0, 150)}{text.length > 150 ? '...' : ''}
        </p>
      )}
      
      {/* Why this matters */}
      {!expanded && (rootCause || resolution) && (
        <div className="mt-3 pt-3 border-t border-primary/20">
          <p className="text-xs text-cyan-300 italic">
            💡 This historical resolution is relevant to your current incident
          </p>
        </div>
      )}
    </div>
  );
}
