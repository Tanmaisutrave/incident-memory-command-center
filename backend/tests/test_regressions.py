"""Regression checks run offline: no provider calls or production memory writes."""
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from fastapi.testclient import TestClient
from app.schemas import IncidentCreate, ResolutionRequest, IncidentUpdate, IncidentStatus
from app.services.analysis_service import AnalysisService
from app.services.incident_service import IncidentService

INCIDENT = dict(title='TLS certificate expired', service='gateway', environment='production', severity='P2', symptoms='Partner requests fail certificate verification, internal requests are healthy.')
DIAGNOSIS = dict(summary='Certificate failure needs verification.', likely_root_cause='Expired partner certificate.', evidence_assessment='Reported error supports an unconfirmed hypothesis.', investigation_steps=['Check certificate validity dates.'], recommended_actions=['Renew only if expiry is confirmed.'], disconfirming_checks=['A valid certificate would contradict expiration.'], verification_steps=['Verify handshake and successful requests.'], historical_evidence=[], memory_insights=[], cited_sources=[], risk_notes='Do not disable TLS verification.')
RESOLUTION = dict(root_cause='Certificate expiry confirmed', resolution='Partner renewed certificate', actions_taken=['Verified the new certificate'], outcome='successfully_resolved')

def analyzer(memories=None, diagnosis=None):
    svc=AnalysisService()
    svc.memory=SimpleNamespace(recall_similar_incidents=Mock(return_value=memories or []))
    svc.llm=SimpleNamespace(generate_json=Mock(return_value=json.dumps(diagnosis or DIAGNOSIS)))
    return svc

def test_non_database_diagnosis_and_no_invented_confidence():
    result=analyzer().analyze_incident({'incident_id':'test',**INCIDENT})
    assert result.likely_root_cause=='Expired partner certificate.'
    assert result.confidence is None and result.memory_status=='empty' and not result.used_memory
    assert 'pool' not in str(result.model_dump()).lower()

def test_malformed_output_is_rejected():
    svc=analyzer(); svc.llm.generate_json.return_value='TLS certificate expired.'
    with pytest.raises(RuntimeError, match='No diagnosis was substituted'):
        svc.analyze_incident({'incident_id':'test',**INCIDENT})

def test_unknown_source_is_rejected():
    svc=analyzer(diagnosis={**DIAGNOSIS,'cited_sources':['invented']})
    with pytest.raises(RuntimeError,match='unknown memory'):
        svc.analyze_incident({'incident_id':'test',**INCIDENT})

def test_memory_failure_differs_from_empty():
    svc=analyzer(); svc.memory.recall_similar_incidents.side_effect=RuntimeError('offline')
    result=svc.analyze_incident({'incident_id':'test',**INCIDENT})
    assert result.memory_status=='unavailable' and result.warnings and not result.used_memory

def test_valid_source_and_timings():
    svc=analyzer([{'text':'A previous TLS failure.', 'type':'world','source_id':'m1'}],{**DIAGNOSIS,'cited_sources':['m1'],'historical_evidence':['m1 describes a TLS failure.']})
    result=svc.analyze_incident({'incident_id':'test',**INCIDENT})
    assert result.used_memory and result.cited_sources==['m1'] and result.timings_ms['total']>=0

def test_current_updates_reach_model():
    svc=analyzer();svc.analyze_incident({'incident_id':'test',**INCIDENT,'updates':[{'note':'Renewal did not fix it','kind':'failed_attempt'}]})
    assert 'Renewal did not fix it' in svc.llm.generate_json.call_args.args[0]

def test_resolution_delivery_and_restart(tmp_path):
    svc=IncidentService(tmp_path/'incidents.db')
    svc.memory=SimpleNamespace(retain_resolved_incident=Mock(return_value=False))
    item=svc.create_incident(IncidentCreate(**INCIDENT))
    result=svc.resolve_incident(item.incident_id,ResolutionRequest(**RESOLUTION))
    assert not result.memory_retained and result.status==IncidentStatus.RESOLVED
    restored=IncidentService(tmp_path/'incidents.db').require(item.incident_id)
    assert restored.resolution==RESOLUTION['resolution'] and not restored.memory_retained

@pytest.mark.parametrize('outcome,status',[('partially_resolved','mitigated'),('unresolved_escalated','escalated')])
def test_unsuccessful_outcome_not_resolved(tmp_path,outcome,status):
    svc=IncidentService(tmp_path/'incidents.db');svc.memory=SimpleNamespace(retain_resolved_incident=Mock(return_value=True))
    item=svc.create_incident(IncidentCreate(**INCIDENT))
    result=svc.resolve_incident(item.incident_id,ResolutionRequest(**{**RESOLUTION,'outcome':outcome}))
    assert result.status.value==status and result.resolved_at is None

def test_update_saved_when_memory_is_down(tmp_path):
    svc=IncidentService(tmp_path/'incidents.db')
    retain=Mock(side_effect=RuntimeError('offline'))
    svc.memory=SimpleNamespace(hindsight=SimpleNamespace(retain=retain))
    item=svc.create_incident(IncidentCreate(**INCIDENT))
    item.analysis={'summary':'Previous advice'}
    svc._save(item)
    result=svc.add_update(item.incident_id,IncidentUpdate(note='Renewing did not fix the failure.',kind='failed_attempt'))
    assert not result.memory_retained and len(result.updates)==1 and result.analysis is None
    retain.side_effect=None;retain.return_value={'success':True}
    assert svc.retry_memory(item.incident_id).memory_retained
    assert retain.call_args.kwargs['document_id']==item.incident_id

def test_compare_parallel_and_no_persisted_incident(tmp_path):
    svc=IncidentService(tmp_path/'incidents.db');barrier=Barrier(2)
    def analyze(incident,use_memory):
        barrier.wait(timeout=2)
        return use_memory
    svc.analysis=SimpleNamespace(analyze_incident=analyze)
    result=svc.compare_analysis(IncidentCreate(**INCIDENT))
    assert result=={'without_memory':False,'with_memory':True}
    assert svc.list_incidents()==[]

def test_api_contracts_and_error_delivery(tmp_path,monkeypatch):
    from app import main
    svc=IncidentService(tmp_path/'incidents.db');svc.analysis=analyzer()
    svc.memory=SimpleNamespace(retain_resolved_incident=Mock(return_value=False))
    monkeypatch.setattr(main,'incident_service',svc)
    with TestClient(main.app) as client:
        result=client.post('/api/incidents/analyze',json=INCIDENT)
        assert result.status_code==200
        key=result.json()['incident_id']
        outcome=client.post(f'/api/incidents/{key}/resolve',json=RESOLUTION)
        assert outcome.status_code==200 and not outcome.json()['memory_retained']
        assert client.post('/api/incidents/compare',json={'incident':INCIDENT}).status_code==200
        assert client.post('/api/incidents/compare',json={'incident_id_1':'a','incident_id_2':'b'}).status_code==422
        assert client.get('/api/incidents').json()[0]['analysis']


def test_hindsight_acknowledgement_and_client_cleanup(monkeypatch):
    from app import hindsight_client as module
    from unittest.mock import MagicMock
    client = MagicMock()
    client.__enter__.return_value = client
    monkeypatch.setattr(module.settings, 'hindsight_api_key', 'test-key')
    monkeypatch.setattr(module, 'Hindsight', Mock(return_value=client))
    wrapper = module.HindsightClient()
    client.retain.return_value = SimpleNamespace(success=True, var_async=True)
    assert wrapper.retain('synthetic')['success'] is False
    client.retain.return_value = SimpleNamespace(success=True, var_async=False)
    assert wrapper.retain('synthetic')['success'] is True
    assert client.__exit__.call_count == 2


def test_groq_uses_strict_schema_without_extra_model_call():
    from app.llm import LLMClient
    from app.schemas import Diagnosis
    client = LLMClient()
    client.generate = Mock(return_value='{}')
    schema = Diagnosis.model_json_schema()
    client.generate_json('synthetic incident', schema=schema)
    fmt = client.generate.call_args.kwargs['response_format']
    assert fmt['type'] == 'json_schema' and fmt['json_schema']['strict']
    assert fmt['json_schema']['schema']['additionalProperties'] is False
    assert client.generate.call_count == 1
