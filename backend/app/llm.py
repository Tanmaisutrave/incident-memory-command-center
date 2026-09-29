"""Groq structured generation: bounded requests, no invented parser fallbacks."""
import json
from groq import Groq
from app.config import settings


class LLMClient:
    def __init__(self):
        self.model = settings.groq_model
        self.client = None

    def _client(self):
        if not settings.groq_api_key or settings.groq_api_key.startswith('your_'):
            raise RuntimeError('Set GROQ_API_KEY in backend/.env, then restart the backend.')
        if self.client is None:
            self.client = Groq(api_key=settings.groq_api_key, timeout=45.0, max_retries=0)
        return self.client

    def generate(self, prompt, system_prompt=None, temperature=0.1, max_tokens=1800, response_format=None):
        messages = []
        if system_prompt:
            messages.append({'role': 'system', 'content': system_prompt})
        messages.append({'role': 'user', 'content': prompt})
        options = {'response_format': response_format} if response_format else {}
        response = self._client().chat.completions.create(
            model=self.model, messages=messages, temperature=temperature,
            max_tokens=max_tokens, **options)
        if response.choices[0].finish_reason == 'length':
            raise RuntimeError('The model response was incomplete. Try a shorter incident description.')
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError('The model returned an empty response. Please retry.')
        return content

    def generate_json(self, prompt, system_prompt=None, temperature=0.1, max_tokens=2400, schema=None):
        # Provider-side schema enforcement avoids costly malformed-output retries.
        return self.generate(prompt, system_prompt, temperature, max_tokens,
            response_format={'type': 'json_schema', 'json_schema': {
                'name': 'incident_diagnosis', 'strict': True, 'schema': schema}})

    def health_check(self):
        self._client().models.list()
        return True


llm_client = LLMClient()
