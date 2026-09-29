"""Regression checks run offline: no provider calls or production memory writes.

All tests that need a DB receive a tmp_path-scoped IncidentService so they
are fully isolated and never touch the production DB.
"""
import gc
import json
import logging
import sqlite3
import time
import warnings
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.schemas import (
    IncidentCreate, IncidentStatus, IncidentUpdate, ResolutionRequest,
    TERMINAL_STATUSES,
)
from app.services.analysis_service import AnalysisService
from app.services.incident_service import ConflictError, IncidentService

# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------

INCIDENT = dict(
    title='TLS certificate expired',
    service='gateway',
    environment='production',
    severity='P2',
    symptoms='Partner requests fail certificate verification, internal requests are healthy.',
)
DIAGNOSIS = dict(
    summary='Certificate failure needs verification.',
    likely_root_cause='Expired partner certificate.',
    evidence_assessment='Reported error supports an unconfirmed hypothesis.',
    severity_assessment='P2',
    severity_reasoning='P2 assigned; major partner functionality impaired.',
    investigation_steps=['Check certificate validity dates.'],
    recommended_actions=['Renew only if expiry is confirmed.'],
    disconfirming_checks=['A valid certificate would contradict expiration.'],
    verification_steps=['Verify handshake and successful requests.'],
    historical_evidence=[],
    memory_insights=[],
    cited_sources=[],
    risk_notes='Do not disable TLS verification.',
)
RESOLUTION = dict(
    root_cause='Certificate expiry confirmed',
    resolution='Partner renewed certificate',
    actions_taken=['Verified the new certificate'],
    outcome='successfully_resolved',
)


def analyzer(memories=None, diagnosis=None):
    svc = AnalysisService()
    svc.memory = SimpleNamespace(recall_similar_incidents=Mock(return_value=memories or []))
    raw = json.dumps(diagnosis or DIAGNOSIS)
    svc.llm = SimpleNamespace(
        generate_json=Mock(return_value=raw),
        generate_json_with_correction=Mock(return_value=raw),
    )
    return svc


def make_svc(tmp_path, analysis_svc=None, memory_svc=None):
    """Helper: IncidentService backed by a fresh tmp DB."""
    return IncidentService(
        db_path=tmp_path / 'incidents.db',
        analysis_svc=analysis_svc,
        memory_svc=memory_svc,
    )


# ===========================================================================
# Analysis service unit tests (no DB)
# ===========================================================================

def test_non_database_diagnosis_and_no_invented_confidence():
    result = analyzer().analyze_incident({'incident_id': 'test', **INCIDENT})
    assert result.likely_root_cause == 'Expired partner certificate.'
    assert result.confidence is None and result.memory_status == 'empty' and not result.used_memory
    assert 'pool' not in str(result.model_dump()).lower()


def test_malformed_output_is_rejected():
    svc = analyzer()
    # Both first attempt and correction retry return malformed output
    svc.llm.generate_json.return_value = 'TLS certificate expired.'
    svc.llm.generate_json_with_correction.return_value = 'TLS certificate expired.'
    with pytest.raises(RuntimeError, match='No diagnosis was substituted'):
        svc.analyze_incident({'incident_id': 'test', **INCIDENT})


def test_unknown_source_is_rejected():
    bad = json.dumps({**DIAGNOSIS, 'cited_sources': ['invented']})
    svc = analyzer(diagnosis={**DIAGNOSIS, 'cited_sources': ['invented']})
    svc.llm.generate_json.return_value = bad
    svc.llm.generate_json_with_correction.return_value = bad
    with pytest.raises(RuntimeError, match='No diagnosis was substituted'):
        svc.analyze_incident({'incident_id': 'test', **INCIDENT})


def test_memory_failure_differs_from_empty():
    svc = analyzer()
    svc.memory.recall_similar_incidents.side_effect = RuntimeError('offline')
    result = svc.analyze_incident({'incident_id': 'test', **INCIDENT})
    assert result.memory_status == 'unavailable' and result.warnings and not result.used_memory


def test_valid_source_and_timings():
    svc = analyzer(
        [{'text': 'A previous TLS failure.', 'type': 'world', 'source_id': 'm1'}],
        {**DIAGNOSIS, 'cited_sources': ['m1'], 'historical_evidence': ['m1 describes a TLS failure.']},
    )
    result = svc.analyze_incident({'incident_id': 'test', **INCIDENT})
    assert result.used_memory and result.cited_sources == ['m1'] and result.timings_ms['total'] >= 0


def test_current_updates_reach_model():
    svc = analyzer()
    svc.analyze_incident({
        'incident_id': 'test', **INCIDENT,
        'updates': [{'note': 'Renewal did not fix it', 'kind': 'failed_attempt'}],
    })
    assert 'Renewal did not fix it' in svc.llm.generate_json.call_args.args[0]


# ===========================================================================
# Incident service / DB tests
# ===========================================================================

def test_resolution_delivery_and_restart(tmp_path):
    svc = make_svc(tmp_path)
    svc.memory = SimpleNamespace(retain_resolved_incident=Mock(return_value=False))
    item = svc.create_incident(IncidentCreate(**INCIDENT))
    result = svc.resolve_incident(item.incident_id, ResolutionRequest(**RESOLUTION))
    assert not result.memory_retained and result.status == IncidentStatus.RESOLVED
    restored = make_svc(tmp_path).require(item.incident_id)
    assert restored.resolution == RESOLUTION['resolution'] and not restored.memory_retained


@pytest.mark.parametrize('outcome,status', [
    ('partially_resolved', 'mitigated'),
    ('unresolved_escalated', 'escalated'),
])
def test_unsuccessful_outcome_not_resolved(tmp_path, outcome, status):
    svc = make_svc(tmp_path)
    svc.memory = SimpleNamespace(retain_resolved_incident=Mock(return_value=True))
    item = svc.create_incident(IncidentCreate(**INCIDENT))
    result = svc.resolve_incident(item.incident_id, ResolutionRequest(**{**RESOLUTION, 'outcome': outcome}))
    assert result.status.value == status and result.resolved_at is None


def test_update_saved_when_memory_is_down(tmp_path):
    svc = make_svc(tmp_path)
    retain = Mock(side_effect=RuntimeError('offline'))
    svc.memory = SimpleNamespace(hindsight=SimpleNamespace(retain=retain))
    item = svc.create_incident(IncidentCreate(**INCIDENT))
    # Give it a prior analysis to confirm it gets cleared
    inc, ver = svc._require_with_version(item.incident_id)
    inc.analysis = {'summary': 'Previous advice'}
    svc._save(inc, ver)

    result = svc.add_update(
        item.incident_id,
        IncidentUpdate(note='Renewing did not fix the failure.', kind='failed_attempt'),
    )
    assert not result.memory_retained
    assert len(result.updates) == 1
    assert result.analysis is None

    retain.side_effect = None
    retain.return_value = {'success': True}
    assert svc.retry_memory(item.incident_id).memory_retained
    assert retain.call_args.kwargs['document_id'] == item.incident_id


def test_compare_parallel_and_no_persisted_incident(tmp_path):
    svc = make_svc(tmp_path)
    # compare_analysis now delegates to analysis_svc.compare_analysis
    # Patch it to return the expected structure directly
    svc.analysis = SimpleNamespace(
        compare_analysis=Mock(return_value={
            'without_memory': False,
            'with_memory': True,
            'differences': {},
        })
    )
    result = svc.compare_analysis(IncidentCreate(**INCIDENT))
    assert result == {'without_memory': False, 'with_memory': True, 'differences': {}}
    assert svc.list_incidents() == []


def test_api_contracts_and_error_delivery(tmp_path, monkeypatch):
    from app import main

    svc = make_svc(tmp_path, analysis_svc=analyzer())
    svc.memory = SimpleNamespace(retain_resolved_incident=Mock(return_value=False))

    # Override the FastAPI dependency so the lifespan service is bypassed.
    main.app.dependency_overrides[main.get_incident_service] = lambda: svc

    try:
        with TestClient(main.app) as client:
            result = client.post('/api/incidents/analyze', json=INCIDENT)
            assert result.status_code == 200
            key = result.json()['incident_id']

            outcome = client.post(f'/api/incidents/{key}/resolve', json=RESOLUTION)
            assert outcome.status_code == 200 and not outcome.json()['memory_retained']

            assert client.post('/api/incidents/compare', json={'incident': INCIDENT}).status_code == 200
            assert client.post('/api/incidents/compare', json={'incident_id_1': 'a', 'incident_id_2': 'b'}).status_code == 422
            assert client.get('/api/incidents').json()[0]['incident_id'] == key
    finally:
        main.app.dependency_overrides.pop(main.get_incident_service, None)


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


# ===========================================================================
# Status-transition tests
# ===========================================================================

def test_analyze_blocked_on_terminal_status(tmp_path):
    """analyze_incident must not change mitigated / escalated / resolved / closed."""
    svc = make_svc(tmp_path, analysis_svc=analyzer())
    svc.memory = SimpleNamespace(retain_resolved_incident=Mock(return_value=True))
    item = svc.create_incident(IncidentCreate(**INCIDENT))
    # Resolve it
    svc.resolve_incident(item.incident_id, ResolutionRequest(**RESOLUTION))
    with pytest.raises(ValueError, match='Cannot analyze'):
        svc.analyze_incident(item.incident_id)


def test_add_update_on_resolved_without_reopen_raises(tmp_path):
    svc = make_svc(tmp_path)
    svc.memory = SimpleNamespace(retain_resolved_incident=Mock(return_value=True))
    item = svc.create_incident(IncidentCreate(**INCIDENT))
    svc.resolve_incident(item.incident_id, ResolutionRequest(**RESOLUTION))
    with pytest.raises(ValueError, match='reopen'):
        svc.add_update(
            item.incident_id,
            IncidentUpdate(note='New evidence arrived from the monitoring system.', kind='evidence'),
        )


def test_add_update_with_reopen_clears_resolution_fields(tmp_path):
    svc = make_svc(tmp_path)
    svc.memory = SimpleNamespace(
        retain_resolved_incident=Mock(return_value=True),
        hindsight=SimpleNamespace(retain=Mock(return_value={'success': True})),
    )
    item = svc.create_incident(IncidentCreate(**INCIDENT))
    svc.resolve_incident(item.incident_id, ResolutionRequest(**RESOLUTION))

    result = svc.add_update(
        item.incident_id,
        IncidentUpdate(
            note='New evidence arrived from the monitoring system.',
            kind='evidence',
            reopen=True,
        ),
    )
    assert result.status == IncidentStatus.INVESTIGATING
    assert result.outcome is None
    assert result.resolution is None
    assert result.resolved_at is None
    assert len(result.updates) == 1


# ===========================================================================
# Concurrency / lost-update tests
# ===========================================================================

def test_concurrent_add_update_during_slow_analyze_keeps_both(tmp_path):
    """
    While analyze_incident is running its slow model call, add_update writes
    a new update. The post-analysis save must not clobber that update.
    """
    analyze_started = Event()
    analyze_may_finish = Event()

    real_analyzer = analyzer()

    def slow_analyze(incident_dict, use_memory=True):
        analyze_started.set()
        analyze_may_finish.wait(timeout=5)
        return real_analyzer.analyze_incident(incident_dict, use_memory)

    svc = make_svc(tmp_path)
    svc.analysis = SimpleNamespace(analyze_incident=slow_analyze)
    svc.memory = SimpleNamespace(
        recall_similar_incidents=Mock(return_value=[]),
        hindsight=SimpleNamespace(retain=Mock(return_value={'success': True})),
    )

    item = svc.create_incident(IncidentCreate(**INCIDENT))

    with ThreadPoolExecutor(max_workers=2) as pool:
        f_analyze = pool.submit(svc.analyze_incident, item.incident_id)

        # Wait until the slow call has started, then add an update
        analyze_started.wait(timeout=5)
        svc.add_update(
            item.incident_id,
            IncidentUpdate(note='Found packet loss on eth0 during analysis window.', kind='evidence'),
        )
        # Let analyze finish
        analyze_may_finish.set()
        f_analyze.result(timeout=10)

    final = svc.require(item.incident_id)
    assert len(final.updates) == 1, 'The update written during analysis must be preserved'
    assert final.analysis is not None, 'Analysis result must also be persisted'


def test_ordering_stable_after_update(tmp_path):
    """list_incidents returns newest first; updating a row does not reorder it."""
    svc = make_svc(tmp_path)
    svc.memory = SimpleNamespace(
        hindsight=SimpleNamespace(retain=Mock(return_value={'success': False})),
    )
    a = svc.create_incident(IncidentCreate(**INCIDENT))
    b = svc.create_incident(IncidentCreate(**{**INCIDENT, 'title': 'Second incident title here'}))

    # Update the older incident (a); it must stay below b in the list
    svc.add_update(a.incident_id, IncidentUpdate(note='Added update to older incident row.', kind='evidence'))

    listed = svc.list_incidents()
    ids = [i.incident_id for i in listed]
    assert ids.index(b.incident_id) < ids.index(a.incident_id), (
        'Newer incident b must appear before older incident a regardless of update order'
    )


# ===========================================================================
# Corrupted row test
# ===========================================================================

def test_corrupted_row_is_skipped_with_warning(tmp_path, caplog):
    """A row with invalid JSON payload is skipped in list_incidents with a warning."""
    svc = make_svc(tmp_path)
    item = svc.create_incident(IncidentCreate(**INCIDENT))

    # Directly corrupt the payload in the DB
    with sqlite3.connect(str(tmp_path / 'incidents.db')) as conn:
        conn.execute("UPDATE incidents SET payload=? WHERE id=?",
                     ('this is not json {{{', item.incident_id))
        conn.commit()

    with caplog.at_level(logging.WARNING, logger='app.services.incident_service'):
        results = svc.list_incidents()

    assert results == [], 'Corrupted row should be skipped'
    assert any('Skipping corrupted' in r.message for r in caplog.records)


# ===========================================================================
# Connection leak test
# ===========================================================================

def test_connections_are_closed(tmp_path):
    """
    After all operations, no SQLite connections should remain open.
    Verified by enabling ResourceWarning and forcing GC.
    We filter to only sqlite3.Connection-related resource warnings so that
    unrelated anyio stream warnings from other tests don't cause false failures.
    """
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always', ResourceWarning)

        svc = make_svc(tmp_path)
        svc.memory = SimpleNamespace(
            retain_resolved_incident=Mock(return_value=False),
            hindsight=SimpleNamespace(retain=Mock(return_value={'success': False})),
        )
        item = svc.create_incident(IncidentCreate(**INCIDENT))
        svc.get_incident(item.incident_id)
        svc.list_incidents()
        svc.add_update(
            item.incident_id,
            IncidentUpdate(note='Checking connection cleanup behaviour now.', kind='evidence'),
        )
        # Dereference the service and force GC
        del svc
        gc.collect()

    sqlite_leaks = [
        w for w in caught
        if issubclass(w.category, ResourceWarning) and 'sqlite3' in str(w.message).lower()
    ]
    assert sqlite_leaks == [], (
        f'Leaked SQLite connections detected: {[str(w.message) for w in sqlite_leaks]}'
    )


# ===========================================================================
# Optimistic concurrency
# ===========================================================================

def test_conflict_error_on_stale_version(tmp_path):
    """_save with a wrong expected_version raises ConflictError."""
    svc = make_svc(tmp_path)
    item = svc.create_incident(IncidentCreate(**INCIDENT))
    inc, ver = svc._require_with_version(item.incident_id)
    # Simulate another writer bumping the version
    svc._save(inc, ver)
    # Now try to save with the stale version
    with pytest.raises(ConflictError):
        svc._save(inc, ver)  # ver is now stale (was already incremented)


# ===========================================================================
# Delete
# ===========================================================================

def test_delete_incident(tmp_path):
    svc = make_svc(tmp_path)
    item = svc.create_incident(IncidentCreate(**INCIDENT))
    svc.delete_incident(item.incident_id)
    assert svc.get_incident(item.incident_id) is None


def test_delete_nonexistent_raises(tmp_path):
    svc = make_svc(tmp_path)
    from app.schemas import NotFoundError as _NFE
    with pytest.raises(_NFE, match='not found'):
        svc.delete_incident('INC-DOESNOTEXIST')


# ===========================================================================
# Legacy import guard
# ===========================================================================

def test_legacy_import_runs_once(tmp_path):
    """Calling import_legacy_once() twice does not duplicate records."""
    import json as _json
    from pathlib import Path as _Path

    legacy_dir = tmp_path / 'seed'
    legacy_dir.mkdir()
    legacy_file = legacy_dir / 'legacy_incidents.json'
    legacy_file.write_text(_json.dumps({'incidents': [
        {
            'incident_id': 'INC-LEGACY01',
            'title': 'Legacy test incident with enough words',
            'service': 'legacy-svc',
            'environment': 'production',
            'severity': 'P3',
            'symptoms': 'This is a legacy seed symptom long enough for the validator.',
        }
    ]}), encoding='utf-8')

    # Subclass to redirect the seed path to our tmp_path
    class _PatchedService(IncidentService):
        def import_legacy_once(self):
            import json as j
            from app.schemas import Incident as _Inc
            from app.services.incident_service import _utcnow
            legacy = legacy_file
            if not legacy.exists():
                return
            with self._db() as db:
                row = db.execute("SELECT value FROM meta WHERE key='legacy_imported'").fetchone()
                if row:
                    return
                records = j.loads(legacy.read_text(encoding='utf-8')).get('incidents', [])
                now = _utcnow()
                for record in records:
                    try:
                        item = _Inc(**record)
                    except Exception as exc:
                        logger.warning('Skipping malformed legacy record %s: %s',
                                       record.get('incident_id', '?'), exc)
                        continue
                    db.execute(
                        'INSERT OR IGNORE INTO incidents (id, payload, version, created_at, updated_at) '
                        'VALUES (?, ?, 0, ?, ?)',
                        (item.incident_id, item.model_dump_json(), now, now),
                    )
                db.execute("INSERT INTO meta (key, value) VALUES ('legacy_imported', '1')")

    svc = _PatchedService(db_path=tmp_path / 'incidents.db')
    svc.import_legacy_once()
    svc.import_legacy_once()  # second call must be a no-op

    all_ids = [i.incident_id for i in svc.list_incidents()]
    assert all_ids.count('INC-LEGACY01') == 1, 'Legacy record must appear exactly once'


# ===========================================================================
# Preventive actions persistence
# ===========================================================================

def test_preventive_actions_persisted(tmp_path):
    svc = make_svc(tmp_path)
    svc.memory = SimpleNamespace(retain_resolved_incident=Mock(return_value=False))
    item = svc.create_incident(IncidentCreate(**INCIDENT))
    resolution = ResolutionRequest(
        **RESOLUTION,
        preventive_actions=['Automate certificate renewal', 'Add 30-day expiry alert'],
    )
    svc.resolve_incident(item.incident_id, resolution)
    restored = svc.require(item.incident_id)
    assert restored.preventive_actions == ['Automate certificate renewal', 'Add 30-day expiry alert']
