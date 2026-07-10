from __future__ import annotations
from abc import ABC, abstractmethod
import json
import urllib.request
import urllib.error

class AIProvider(ABC):
    @abstractmethod
    def analyze(self, prompt: str, documents: list[str]) -> dict: ...

class DisabledProvider(AIProvider):
    def analyze(self, prompt: str, documents: list[str]) -> dict:
        return {'status': 'disabled', 'message': 'ИИ-провайдер не настроен. Использован локальный анализ правил.'}

class OpenAICompatibleProvider(AIProvider):
    """Минимальный адаптер OpenAI-совместимого Responses API без хранения ключа в коде."""
    def __init__(self, api_key: str, base_url: str, model: str, timeout: int = 120):
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.timeout = timeout

    def analyze(self, prompt: str, documents: list[str]) -> dict:
        source = '\n\n--- ДОКУМЕНТ ---\n'.join(documents)
        body = json.dumps({
            'model': self.model,
            'input': [
                {'role': 'system', 'content': [{'type': 'input_text', 'text': prompt}]},
                {'role': 'user', 'content': [{'type': 'input_text', 'text': source[:500000]}]},
            ],
        }, ensure_ascii=False).encode('utf-8')
        request = urllib.request.Request(
            f'{self.base_url}/responses', data=body, method='POST',
            headers={'Authorization': f'Bearer {self.api_key}', 'Content-Type': 'application/json'},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode('utf-8', errors='replace')
            return {'status': 'error', 'message': f'HTTP {exc.code}: {detail[:1000]}'}
        except Exception as exc:
            return {'status': 'error', 'message': str(exc)}
        text_parts = []
        for output in payload.get('output', []):
            for content in output.get('content', []):
                if content.get('type') == 'output_text':
                    text_parts.append(content.get('text', ''))
        return {'status': 'ok', 'text': '\n'.join(text_parts), 'raw_id': payload.get('id', '')}
