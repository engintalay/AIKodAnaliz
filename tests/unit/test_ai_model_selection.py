"""GELIS24 testleri: model seçimi, meta veri ve gerçek yanıt testi.

Sahte (fake) db/session nesneleriyle çalışır; gerçek veritabanını ve ağı
kullanmaz.
"""
import unittest
from unittest.mock import patch

import backend.lmstudio_client as lc
import backend.permission_manager as permission_manager
import backend.routes.ai_settings as ai_settings_route
import backend.routes.user as user_route
from backend.app import app


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=''):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError('no json payload')
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f'HTTP {self.status_code}')


class FakeSession:
    """URL sonekine göre yanıt döndüren sahte requests.Session."""

    def __init__(self, get_map=None, post_map=None):
        self.get_map = get_map or {}
        self.post_map = post_map or {}
        self.get_calls = []
        self.post_calls = []
        self.headers = {}

    def get(self, url, timeout=None):
        self.get_calls.append(url)
        for suffix, response in sorted(self.get_map.items(), key=lambda kv: -len(kv[0])):
            if url.endswith(suffix):
                return response
        return FakeResponse(404, {'error': 'not found'})

    def post(self, url, headers=None, json=None, timeout=None):
        self.post_calls.append({'url': url, 'json': json})
        for suffix, response in sorted(self.post_map.items(), key=lambda kv: -len(kv[0])):
            if url.endswith(suffix):
                return response
        return FakeResponse(404, {'error': 'not found'})


class FakeRuntimeDB:
    def __init__(self, ai_rows=None, user_row=None):
        self.ai_rows = ai_rows or []
        self.user_row = user_row

    def execute_query(self, sql, params=None):
        if 'user_settings' in sql:
            return [self.user_row] if self.user_row is not None else []
        return list(self.ai_rows)

    def execute_update(self, sql, params=None):
        pass


def _ai_row(name, value, dtype='string'):
    return {'setting_name': name, 'setting_value': value, 'data_type': dtype}


def _client(ai_rows=None, user_row=None):
    original = lc.db
    lc.db = FakeRuntimeDB(ai_rows=ai_rows, user_row=user_row)
    try:
        return lc.LMStudioClient()
    finally:
        lc.db = original


class TestModelMetadata(unittest.TestCase):
    """list_models_with_metadata: OpenAI + LM Studio + llama.cpp birleşimi."""

    def _client_with(self, get_map):
        client = _client()
        client.api_url = 'http://ai:1234/v1'
        client.session = FakeSession(get_map=get_map)
        return client

    def test_openai_models_are_normalized(self):
        client = self._client_with({
            '/models': FakeResponse(200, {
                'data': [
                    {'id': 'model-a', 'context_length': 8192},
                    {'id': 'model-b', 'max_output_tokens': 2048},
                ]
            }),
        })
        result = client.list_models_with_metadata()
        self.assertIsNone(result['error'])
        self.assertEqual([m['id'] for m in result['models']], ['model-a', 'model-b'])
        self.assertEqual(result['models'][0]['context_length'], 8192)
        self.assertEqual(result['models'][1]['max_output_tokens'], 2048)

    def test_vllm_max_input_tokens_is_context_length(self):
        """vLLM /models yanıtı max_input_tokens alanını kullanır."""
        client = self._client_with({
            '/models': FakeResponse(200, {
                'data': [{
                    'id': 'Qwen3.8-Flash-Next',
                    'max_input_tokens': 262144,
                    'max_output_tokens': 131072,
                }]
            }),
        })
        model = client.list_models_with_metadata()['models'][0]
        self.assertEqual(model['context_length'], 262144)
        self.assertEqual(model['max_output_tokens'], 131072)
        self.assertEqual(model['suggested_max_tokens'], 131072)

    def test_vllm_provider_skips_native_metadata_endpoints(self):
        """vLLM/OpenAI sağlayıcılarında yalnız /models çağrılır."""
        client = self._client_with({
            '/models': FakeResponse(200, {'data': [{'id': 'm1'}]}),
        })
        client.provider = 'vllm'
        client.list_models_with_metadata()
        self.assertEqual(client.session.get_calls, ['http://ai:1234/v1/models'])

    def test_openai_provider_skips_native_metadata_endpoints(self):
        client = self._client_with({
            '/models': FakeResponse(200, {'data': [{'id': 'm1'}]}),
        })
        client.provider = 'openai'
        client.list_models_with_metadata()
        self.assertEqual(client.session.get_calls, ['http://ai:1234/v1/models'])

    def test_lmstudio_metadata_enriches_models(self):
        client = self._client_with({
            '/models': FakeResponse(200, {'data': [{'id': 'model-a'}]}),
            '/api/v0/models': FakeResponse(200, {
                'data': [{
                    'id': 'model-a',
                    'max_context_length': 32768,
                    'state': 'loaded',
                    'quantization': 'Q4_K_M',
                    'publisher': 'acme',
                    'arch': 'llama',
                }]
            }),
        })
        model = client.list_models_with_metadata()['models'][0]
        self.assertEqual(model['context_length'], 32768)
        self.assertEqual(model['state'], 'loaded')
        self.assertEqual(model['quantization'], 'Q4_K_M')
        self.assertEqual(model['publisher'], 'acme')
        self.assertEqual(model['arch'], 'llama')

    def test_llamacpp_props_supply_limits_and_defaults(self):
        client = self._client_with({
            '/models': FakeResponse(200, {'data': [{'id': 'local.gguf'}]}),
            '/props': FakeResponse(200, {
                'model_path': '/models/local.gguf',
                'default_generation_settings': {
                    'n_ctx': 4096,
                    'n_predict': 512,
                    'temperature': 0.2,
                    'top_p': 0.8,
                    'top_k': 40,
                    'repeat_penalty': 1.1,
                },
            }),
        })
        model = client.list_models_with_metadata()['models'][0]
        self.assertEqual(model['context_length'], 4096)
        self.assertEqual(model['max_output_tokens'], 512)
        self.assertEqual(model['defaults']['max_tokens'], 512)
        self.assertEqual(model['defaults']['temperature'], 0.2)
        self.assertEqual(model['suggested_max_tokens'], 512)

    def test_suggested_max_tokens_falls_back_to_context_cap(self):
        client = self._client_with({
            '/models': FakeResponse(200, {
                'data': [
                    {'id': 'big', 'context_length': 32768},
                    {'id': 'small', 'context_length': 1024},
                    {'id': 'unknown'},
                ]
            }),
        })
        models = {m['id']: m for m in client.list_models_with_metadata()['models']}
        self.assertEqual(models['big']['suggested_max_tokens'], 4096)
        self.assertEqual(models['small']['suggested_max_tokens'], 1024)
        self.assertIsNone(models['unknown']['suggested_max_tokens'])

    def test_unreachable_server_returns_error_not_exception(self):
        client = self._client_with({'/models': FakeResponse(500, {'error': 'boom'})})
        result = client.list_models_with_metadata()
        self.assertEqual(result['models'], [])
        self.assertIsNotNone(result['error'])


class TestGenerationTest(unittest.TestCase):
    """test_generation: gerçek sohbet tamamlama doğrulaması."""

    def _client_with(self, get_map=None, post_map=None):
        client = _client()
        client.api_url = 'http://ai:1234/v1'
        client.model = 'model-a'
        client.session = FakeSession(get_map=get_map, post_map=post_map)
        return client

    def test_successful_reply(self):
        client = self._client_with(post_map={
            '/chat/completions': FakeResponse(200, {
                'choices': [{'message': {'content': 'OK'}, 'finish_reason': 'stop'}],
                'usage': {'prompt_tokens': 5, 'completion_tokens': 1, 'total_tokens': 6},
            }),
        })
        result = client.test_generation()
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['reply'], 'OK')
        self.assertFalse(result['reasoning_only'])
        self.assertEqual(result['total_tokens'], 6)
        self.assertEqual(client.session.post_calls[0]['json']['max_tokens'], 256)
        self.assertEqual(client.session.post_calls[0]['json']['temperature'], 0)

    def test_reasoning_only_reply_is_accepted(self):
        """Reasoning modelleri bütçeyi reasoning_content'te harcayabilir."""
        client = self._client_with(post_map={
            '/chat/completions': FakeResponse(200, {
                'choices': [{
                    'message': {'content': '\n\n', 'reasoning_content': 'OK yazmam yeterli.'},
                    'finish_reason': 'length',
                }],
            }),
        })
        result = client.test_generation()
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['reply'], 'OK yazmam yeterli.')
        self.assertTrue(result['reasoning_only'])

    def test_empty_reply_is_error(self):
        client = self._client_with(post_map={
            '/chat/completions': FakeResponse(200, {
                'choices': [{'message': {'content': ''}, 'finish_reason': 'length'}],
            }),
        })
        result = client.test_generation()
        self.assertEqual(result['status'], 'error')
        self.assertIn('boş yanıt', result['error'].lower())

    def test_http_error_is_reported(self):
        client = self._client_with(post_map={
            '/chat/completions': FakeResponse(500, {'error': 'model crashed'}),
        })
        result = client.test_generation()
        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['status_code'], 500)

    def test_invalid_model_retries_with_first_available(self):
        client = self._client_with(
            get_map={'/models': FakeResponse(200, {'data': [{'id': 'fallback-model'}]})},
            post_map={},
        )
        responses = [
            FakeResponse(400, {'error': 'Invalid model identifier'}),
            FakeResponse(200, {'choices': [{'message': {'content': 'OK'}}]}),
        ]

        def _post(url, headers=None, json=None, timeout=None):
            client.session.post_calls.append({'url': url, 'json': json})
            return responses.pop(0)

        client.session.post = _post
        result = client.test_generation()
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['model'], 'fallback-model')
        self.assertEqual(len(client.session.post_calls), 2)


class FakeRouteClient:
    """ai_settings route'unun LocalAIClient yerine kullandığı sahte istemci."""

    instances = []

    def __init__(self, user_id=None):
        self.user_id = user_id
        self.api_url = 'http://global:1234/v1'
        self.api_key = 'GLOBALKEY'
        self.provider = 'lmstudio'
        self.model = 'global-model'
        self.key_calls = []
        FakeRouteClient.instances.append(self)

    def set_api_key(self, key):
        self.api_key = (key or '').strip()
        self.key_calls.append(self.api_key)

    def list_models_with_metadata(self):
        return {'models': [{'id': self.model}], 'api_url': self.api_url,
                'provider': self.provider, 'error': None}

    def test_generation(self, max_tokens=256):
        return {'status': 'ok', 'model': self.model, 'reply': 'OK',
                'latency_ms': 1, 'max_tokens': max_tokens}


class TestRouteOverrides(unittest.TestCase):
    """_build_client_with_overrides: URL değişince global anahtar sızmamalı."""

    def setUp(self):
        FakeRouteClient.instances = []
        self.patches = [
            patch.object(ai_settings_route, 'LocalAIClient', FakeRouteClient),
            patch.object(ai_settings_route, 'get_user_from_session',
                         return_value={'id': 7, 'role': 'admin'}),
            patch.object(permission_manager, 'get_user_from_session',
                         return_value={'id': 7, 'role': 'admin'}),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def test_same_url_keeps_stored_key(self):
        client = ai_settings_route._build_client_with_overrides(
            {'api_url': 'http://global:1234/v1'})
        self.assertEqual(client.api_url, 'http://global:1234/v1')
        self.assertEqual(client.api_key, 'GLOBALKEY')
        self.assertEqual(client.key_calls, [])

    def test_new_url_without_key_does_not_leak_global_key(self):
        client = ai_settings_route._build_client_with_overrides(
            {'api_url': 'http://other:9999/v1'})
        self.assertEqual(client.api_url, 'http://other:9999/v1')
        self.assertEqual(client.api_key, '')
        self.assertEqual(client.key_calls, [''])

    def test_new_url_with_key_uses_that_key(self):
        client = ai_settings_route._build_client_with_overrides(
            {'api_url': 'http://other:9999/v1', 'api_key': 'USERKEY'})
        self.assertEqual(client.api_key, 'USERKEY')

    def test_models_endpoint_returns_metadata(self):
        app.config['TESTING'] = True
        client = app.test_client()
        resp = client.post('/api/ai-settings/models', json={'api_url': 'http://global:1234/v1'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()['models'][0]['id'], 'global-model')

    def test_generation_endpoint_applies_model_override(self):
        app.config['TESTING'] = True
        client = app.test_client()
        resp = client.post('/api/ai-settings/generation/test',
                           json={'model': 'picked-model', 'max_tokens': 16})
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertEqual(body['status'], 'ok')
        self.assertEqual(body['model'], 'picked-model')
        self.assertEqual(body['max_tokens'], 16)


class FakeUserDB:
    def __init__(self, existing=True):
        self.existing = existing
        self.updates = []
        self.inserts = []
        self.queries = []

    def execute_query(self, sql, params=None):
        self.queries.append((sql, params))
        if 'FROM users u' in sql:
            return [{
                'id': 7, 'username': 'u', 'role': 'admin', 'full_name': 'U',
                'email': 'u@example.com', 'theme': 'light',
                'notifications_enabled': 1, 'items_per_page': 20,
                'default_filter': None, 'ai_api_url': 'http://user:1/v1',
                'ai_api_key': 'USERKEY1234', 'ai_model': 'user-model',
                'preferences': None,
            }]
        if 'SELECT id FROM user_settings' in sql:
            return [{'id': 1}] if self.existing else []
        return []

    def execute_update(self, sql, params=None):
        self.updates.append((sql, tuple(params) if params else params))

    def execute_insert(self, sql, params=None):
        self.inserts.append((sql, tuple(params) if params else params))


class TestUserModelPersistence(unittest.TestCase):
    """user_settings.ai_model GET/PUT davranışı."""

    def setUp(self):
        app.config['TESTING'] = True
        self.client = app.test_client()
        self.fake_db = FakeUserDB()
        self.patches = [
            patch.object(user_route, 'db', self.fake_db),
            patch.object(user_route, 'get_user_from_session',
                         return_value={'id': 7, 'role': 'admin'}),
            patch.object(permission_manager, 'get_user_from_session',
                         return_value={'id': 7, 'role': 'admin'}),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def test_get_returns_ai_model(self):
        resp = self.client.get('/api/users/settings')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()['ai_model'], 'user-model')

    def test_put_saves_ai_model(self):
        resp = self.client.put('/api/users/settings', json={'ai_model': 'new-model'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(self.fake_db.updates), 1)
        sql, params = self.fake_db.updates[0]
        self.assertIn('ai_model = ?', sql)
        self.assertIn('new-model', params)

    def test_put_empty_ai_model_clears_to_null(self):
        resp = self.client.put('/api/users/settings', json={'ai_model': ''})
        self.assertEqual(resp.status_code, 200)
        sql, params = self.fake_db.updates[0]
        self.assertIn('ai_model = ?', sql)
        self.assertIn(None, params)


if __name__ == '__main__':
    unittest.main()
