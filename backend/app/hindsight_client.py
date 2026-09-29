"""Bounded Hindsight requests with explicit connection cleanup."""
from hindsight_client import Hindsight
from app.config import settings


class HindsightClient:
    def __init__(self):
        self.bank_id = settings.hindsight_bank_id

    @property
    def client(self):
        if not settings.hindsight_api_key or settings.hindsight_api_key.startswith('your_'):
            raise RuntimeError('Set HINDSIGHT_API_KEY in backend/.env, then restart the backend.')
        return Hindsight(base_url=settings.hindsight_base_url,
            api_key=settings.hindsight_api_key, timeout=35)

    def retain(self, content, metadata=None, context=None, document_id=None):
        with self.client as client:
            result = client.retain(bank_id=self.bank_id, content=content,
            metadata={k: str(v) for k, v in (metadata or {}).items()},
            context=context, document_id=document_id or (metadata or {}).get('incident_id'))
        return {'success': bool(result.success and not result.var_async), 'result': result}

    def recall(self, query, max_tokens=2400, budget='mid'):
        with self.client as client:
            response = client.recall(bank_id=self.bank_id, query=query,
            max_tokens=max_tokens, budget=budget)
        return [{'text': m.text, 'type': str(m.type), 'source_id': str(getattr(m, 'id', '') or f'M{i+1}')}
                for i, m in enumerate(response.results)]

    def reflect(self, query, budget='low', context=None):
        with self.client as client:
            return client.reflect(bank_id=self.bank_id, query=query, budget=budget,
            context=context, max_tokens=1200).text

    def health_check(self):
        import httpx
        response = httpx.get(settings.hindsight_base_url.rstrip('/') + '/health/ready',
            headers={'Authorization': f'Bearer {settings.hindsight_api_key}'}, timeout=5)
        return response.is_success


hindsight_client = HindsightClient()
