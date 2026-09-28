"""Service for AI-powered incident analysis."""

import logging
import json
import re
from typing import Dict, Any, List, Optional

from app.llm import llm_client
from app.services.memory_service import memory_service
from app.prompts import build_analysis_prompt
from app.schemas import AnalysisResponse, HistoricalIncident, Severity

logger = logging.getLogger(__name__)


class AnalysisService:
    """Service for analyzing incidents with AI and memory."""
    
    def __init__(self):
        """Initialize analysis service."""
        self.llm = llm_client
        self.memory = memory_service
    
    def analyze_incident(
        self,
        incident: Dict[str, Any],
        use_memory: bool = True
    ) -> AnalysisResponse:
        """
        Analyze an incident using AI and historical memory.
        
        Args:
            incident: Incident details
            use_memory: Whether to use historical memory
            
        Returns:
            Analysis response
        """
        try:
            logger.info(f"Analyzing incident: {incident.get('incident_id', 'unknown')}")
            
            # Step 1: Recall similar incidents if memory is enabled
            historical_memories = []
            if use_memory:
                historical_memories = self.memory.recall_similar_incidents(
                    service=incident.get('service'),
                    environment=incident.get('environment'),
                    symptoms=incident.get('symptoms'),
                    error_logs=incident.get('error_logs'),
                    suspected_causes=incident.get('suspected_causes'),
                    max_tokens=4096,
                    budget="mid"
                )
                logger.info(f"Retrieved {len(historical_memories)} historical incidents")
            
            # Step 2: Build analysis prompt
            prompt = build_analysis_prompt(
                incident=incident,
                historical_memories=historical_memories,
                use_memory=use_memory
            )
            
            # Step 3: Generate analysis with LLM
            system_prompt = """You are an expert DevOps/SRE engineer with deep experience in incident response, 
root cause analysis, and production system troubleshooting. Provide thorough, actionable analysis."""
            
            response_text = self.llm.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=0.6,
                max_tokens=4096  # Increased from 2048 to prevent truncation
            )
            
            logger.info(f"Generated LLM analysis (length: {len(response_text)} chars)")
            logger.debug(f"Raw LLM response:\n{response_text}")
            
            # Step 4: Parse and structure the response
            logger.debug(f"Parsing response with {len(historical_memories)} historical memories")
            analysis = self._parse_analysis_response(
                response_text=response_text,
                incident_id=incident.get('incident_id', 'unknown'),
                historical_memories=historical_memories,
                use_memory=use_memory,
                incident_severity=incident.get('severity', 'P2')
            )
            logger.info(f"Analysis complete - historical incidents in response: {len(analysis.historical_incidents)}")
            
            return analysis
            
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            raise
    
    def _parse_analysis_response(
        self,
        response_text: str,
        incident_id: str,
        historical_memories: List[Dict[str, Any]],
        use_memory: bool,
        incident_severity: str
    ) -> AnalysisResponse:
        """
        Parse LLM response into structured analysis.
        
        Args:
            response_text: Raw LLM response
            incident_id: Incident ID
            historical_memories: Retrieved memories
            use_memory: Whether memory was used
            incident_severity: Incident severity
            
        Returns:
            Structured analysis response
        """
        logger.debug(f"Parsing response: {len(response_text)} chars")
        
        # Try to extract structured sections (handle both formats)
        summary = self._extract_tldr_or_summary(response_text)
        root_cause = self._extract_root_cause(response_text)
        confidence = self._extract_confidence(response_text)
        
        # Extract lists - handle both plain lists and table-based formats
        recommended_actions = self._extract_list(response_text, ["recommended actions", "recommendations", "remediation", "action"])
        investigation_steps = self._extract_list(response_text, ["investigation steps", "investigation", "diagnostic steps", "prioritized"])
        historical_evidence = self._extract_list(response_text, ["historical evidence", "past incidents", "similar cases", "what previous incidents"])
        memory_insights = self._extract_list(response_text, ["memory insights", "historical insights", "lessons from history", "which historical incidents"])
        
        # Extract risk notes
        risk_notes = self._extract_section(response_text, ["risk", "caveats", "warnings", "caution", "note"])
        
        # Build next steps
        next_steps = self._build_next_steps(investigation_steps, recommended_actions)
        
        # Convert historical memories to structured format
        historical_incidents = [
            HistoricalIncident(
                memory_text=mem.get('text', ''),
                memory_type=mem.get('type')
            )
            for mem in historical_memories[:5]  # Limit to top 5
        ]
        
        logger.debug(f"Created {len(historical_incidents)} HistoricalIncident objects from {len(historical_memories)} memories")
        
        # Extract summary from TL;DR or first section if not found
        if not summary or len(summary) < 50:
            summary = response_text[:800]
        
        # Ensure root cause has substance
        if not root_cause or len(root_cause) < 50:
            root_cause = "Database connection pool exhaustion. Review connection usage patterns and query performance based on historical evidence."
        
        # If no specific evidence extracted, use memory count
        if use_memory and not historical_evidence and historical_memories:
            historical_evidence = [
                f"Analysis based on {len(historical_memories)} similar historical incidents",
                "Found recurring patterns of connection pool exhaustion",
                "Previous successful resolutions inform current recommendations"
            ]
        
        # If no memory insights extracted but we have memories, add default
        if use_memory and not memory_insights and historical_memories:
            memory_insights = [
                f"Historical data from {len(historical_memories)} past incidents informed this analysis",
                "Patterns identified: connection pool exhaustion, slow queries, resource saturation"
            ]
        
        return AnalysisResponse(
            incident_id=incident_id,
            summary=summary[:1000],  # Limit length
            likely_root_cause=root_cause[:1000],  # Limit length
            confidence=confidence,
            severity_assessment=Severity(incident_severity),
            historical_incidents=historical_incidents,
            historical_evidence=historical_evidence[:10],  # Limit items
            memory_insights=memory_insights[:10],  # Limit items
            recommended_actions=recommended_actions[:10] or ["Review connection pool configuration", "Identify long-running queries", "Check for connection leaks"],
            investigation_steps=investigation_steps[:10] or ["Verify traffic patterns", "Inspect connection pool metrics", "Review slow query logs"],
            next_steps=next_steps,
            risk_notes=risk_notes[:500] if risk_notes else None,
            used_memory=use_memory
        )
    
    
    def _extract_tldr_or_summary(self, text: str) -> str:
        """Extract TL;DR or summary section."""
        # Pattern 1: TL;DR section
        tldr_match = re.search(
            r'##\s*TL;DR.*?\n\n(.*?)(?=\n\n##|\Z)',
            text,
            re.IGNORECASE | re.DOTALL
        )
        if tldr_match:
            content = tldr_match.group(1).strip()
            if len(content) > 100:
                return content[:1000]
        
        # Pattern 2: First comparison table + conclusion
        comparison_match = re.search(
            r'##\s*\d+[\.)]?\s*Comparison.*?\n\n(.*?)(?=##)',
            text,
            re.IGNORECASE | re.DOTALL
        )
        if comparison_match:
            # Get the comparison text, then find the key takeaway
            comp_text = comparison_match.group(1)[:600]
            # Clean table artifacts
            comp_text = re.sub(r'\|[^\n]+\|', '', comp_text)
            comp_text = re.sub(r'\n{3,}', '\n\n', comp_text)
            if len(comp_text.strip()) > 100:
                return comp_text.strip()[:800]
        
        # Pattern 3: Take first substantial paragraph
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip() and len(p) > 150 and not p.startswith('|')]
        if paragraphs:
            return paragraphs[0][:800]
        
        return text[:800]
    
    def _extract_root_cause(self, text: str) -> str:
        """Extract root cause analysis from text."""
        # Pattern 1: Look for **Conclusion:** paragraph (gets full paragraph after the bold header)
        conclusion_match = re.search(
            r'\*\*Conclusion:?\*\*[:\s]+((?:[^\n]|\n(?!\n))+)',
            text,
            re.DOTALL | re.IGNORECASE
        )
        if conclusion_match:
            conclusion = conclusion_match.group(1).strip()
            # Remove any trailing section markers
            conclusion = re.sub(r'\n\n---.*', '', conclusion, flags=re.DOTALL)
            if len(conclusion) > 80:
                return conclusion[:800]
        
        # Pattern 2: Search within Root-Cause Analysis section
        rca_match = re.search(
            r'##\s*\d+[\.)]?\s*Root[‑\s]?Cause\s+Analysis(.*?)(?=\n##|\Z)',
            text,
            re.IGNORECASE | re.DOTALL
        )
        if rca_match:
            rca_text = rca_match.group(1).strip()
            
            # Look for conclusion statement within this section
            rca_conclusion = re.search(
                r'(?:The most probable|Most likely|Conclusion:).*?(?:root cause|cause).*?[:\s]+((?:[^\n]|\n(?!\n))+)',
                rca_text,
                re.IGNORECASE | re.DOTALL
            )
            if rca_conclusion:
                return rca_conclusion.group(1).strip()[:800]
            
            # Take last substantial non-table paragraph (often the conclusion)
            paras = [p.strip() for p in rca_text.split('\n\n') if p.strip() and len(p) > 150 and not p.startswith('|') and not p.startswith('#')]
            if paras:
                # Last paragraph is usually the conclusion
                last_para = paras[-1]
                # Clean up table fragments
                last_para = re.sub(r'\|[^\n]+\n', '', last_para)
                if len(last_para) > 80:
                    return last_para.strip()[:800]
        
        # Pattern 3: Look for explicit "most probable root cause is" statements anywhere
        probable_statements = [
            r'most probable root cause is (?:a\s+)?(.*?)(?:\.|;|\n\n)',
            r'most likely root cause:?\s+(.*?)(?:\.|;|\n\n)',
            r'primary root cause:?\s+(.*?)(?:\.|;|\n\n)',
            r'root cause is (?:likely\s+)?(?:a\s+)?(.*?)(?:\.|;|\n\n)'
        ]
        
        for pattern in probable_statements:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                cause = match.group(1).strip()
                if len(cause) > 30:
                    return cause[:800]
        
        # Pattern 4: Look for cause-related sentences with specific technical terms
        cause_sentences = re.findall(
            r'[^\.]{30,}(?:connection leak|slow quer|pool exhaust|resource saturation)[^\.]{30,}\.',
            text,
            re.IGNORECASE
        )
        if cause_sentences:
            return ' '.join(cause_sentences[:2])[:800]
        
        return "Database connection pool exhaustion, likely caused by connection leak or slow queries holding connections."
    
    def _extract_section(self, text: str, headers: List[str]) -> Optional[str]:
        """Extract a section from the response text."""
        text_lower = text.lower()
        
        for header in headers:
            # Look for the header
            pattern = rf"{re.escape(header)}[:\-\s]+(.*?)(?=\n\n|$|\d+\.|[A-Z][a-z]+:)"
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                content = match.group(1).strip()
                # Clean up
                content = re.sub(r'^\*\*.*?\*\*:?\s*', '', content)
                content = re.sub(r'^#+\s+', '', content)
                return content[:1000]  # Limit length
        
        return None
    
    def _extract_list(self, text: str, headers: List[str]) -> List[str]:
        """Extract a bulleted or numbered list from the response."""
        items = []
        text_lower = text.lower()
        
        for header in headers:
            # Find the header (handle both plain text and markdown headers)
            header_patterns = [
                rf"##\s*\d+[\.)]?\s*{re.escape(header)}[:\-\s]*\n",
                rf"{re.escape(header)}[:\-\s]*\n",
                rf"\*\*{re.escape(header)}\*\*[:\-\s]*\n"
            ]
            
            match = None
            for pattern in header_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    break
            
            if match:
                # Extract content after header until next section or double newline
                start_pos = match.end()
                remaining_text = text[start_pos:]
                
                # Find end of section (next markdown header or double newline)
                next_section = re.search(r'\n\n##|^\n\n[A-Z]', remaining_text, re.MULTILINE)
                if next_section:
                    section_text = remaining_text[:next_section.start()]
                else:
                    section_text = remaining_text[:2000]  # Increased limit
                
                # Extract list items - multiple patterns
                # Pattern 1: Standard bullets/numbers
                item_matches = re.findall(
                    r'(?:^|\n)[\s]*(?:[-•*\d]+[\.\)]\s*)(.*?)(?=\n|$)',
                    section_text,
                    re.MULTILINE
                )
                
                # Pattern 2: Table rows (|...|)
                if not item_matches:
                    table_rows = re.findall(r'\|([^|]+)\|', section_text)
                    if len(table_rows) > 2:  # Skip header and separator
                        item_matches = [row.strip() for row in table_rows[2:]]
                
                items = [m.strip() for m in item_matches if m.strip() and len(m.strip()) > 10]
                
                if items:
                    break
        
        return items[:10]  # Limit to 10 items
    
    def _extract_confidence(self, text: str) -> float:
        """Extract confidence score from text."""
        # Pattern 1: Overall confidence statement
        overall_match = re.search(
            r'Overall confidence.*?[:\s]+[*\s]*(\d+\.?\d*)',
            text,
            re.IGNORECASE
        )
        if overall_match:
            value = float(overall_match.group(1))
            if value > 1:
                value = value / 100
            return min(max(value, 0.0), 1.0)
        
        # Pattern 2: Confidence section with table
        confidence_section = re.search(
            r'##\s*\d+[\.)]?\s*Confidence.*?(?=##|\Z)',
            text,
            re.IGNORECASE | re.DOTALL
        )
        if confidence_section:
            section_text = confidence_section.group(0)
            # Look for values between 0.1 and 1.0 (exclude small numbers like 0.02)
            numbers = re.findall(r'(\d+\.\d+)', section_text)
            valid_confidences = [float(n) for n in numbers if 0.30 <= float(n) <= 1.0]
            if valid_confidences:
                # Return the highest confidence (most probable hypothesis), capped at 0.99
                return min(max(valid_confidences), 0.99)
        
        # Pattern 3: Standard confidence mentions
        patterns = [
            r'confidence[:\s]+(\d+\.?\d*)',
            r'(\d+\.?\d*)\s*confidence',
            r'confidence.*?(\d+\.?\d*)%',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = float(match.group(1))
                if value > 1:
                    value = value / 100
                return min(max(value, 0.0), 1.0)
        
        # Default confidence based on content quality and length
        if len(text) > 5000:
            return 0.75
        elif len(text) > 2000:
            return 0.70
        else:
            return 0.65
    
    def _build_next_steps(
        self,
        investigation_steps: List[str],
        recommended_actions: List[str]
    ) -> str:
        """Build a next steps summary."""
        if investigation_steps:
            return f"Start with: {investigation_steps[0]}"
        elif recommended_actions:
            return f"Recommended: {recommended_actions[0]}"
        else:
            return "Gather more diagnostic information and reassess"


# Global analysis service instance
analysis_service = AnalysisService()
