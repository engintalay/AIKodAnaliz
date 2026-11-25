"""GELIS23 testleri: API anahtarı desteği + embedding konfigürasyon ayrımı.

Sahte (fake) db nesneleriyle çalışır; gerçek veritabanını ve ağı kullanmaz.
"""
import time
import unittest

import backend.lmstudio_client as lc
import backend.rag_index as ri
import backend.routes.ai_settings as ai_settings_route
from backend.app import app


class FakeAISettingsDB:
    """ai_settings route'unun kullandığı db yüzeyinin kaydedici sahtesi."""

    def __init__(self, existing=True):
        self.existing = existing
        self.updates = []
        self.inserts = []

    def execute_query(self, sql, params=None):
        if self.existing:
            return [{'id': 1}]
        return []

    def execute_update(self, sql, params=None):
        self.updates.append(tuple(params) if params else params)

    def execute_insert(self, sql, params=None):
        self.inserts.append(tuple(params) if params else params)


class FakeRuntimeDB:
    """LMStudioClient._load_runtime_settings için sahte db."""

    def __init__(self, ai_rows=None, user_row=None):
        self.ai_rows = ai_rows or []
        self.user_row = user_row  # dict or None

    def execute_query(self, sql, params=None):
        if 'user_settings' in sql:
            if self.user_row is None:
                return []
            return [self.user_row]
        return list(self.ai_rows)

    def execute_update(self, sql, params=None):
        pass


def _ai_row(name, value, dtype='string'):
    return {'setting_name': name, 'setting_value': value, 'data_type': dtype}


class TestAuthHeader(unittest.TestCase):
    """Authorization header tek noktadan kurulmalı (lmstudio_client)."""

    def _client(self):
        original = lc.db
        lc.db = FakeRuntimeDB()
        try:
            client = lc.LMStudioClient()
        finally:
            lc.db = original
        return client

    def test_no_key_no_auth_header(self):
        client = self._client()
        client.set_api_key('')
        self.assertNotIn('Authorization', client.session.headers)

    def test_set_api_key_sets_bearer_header(self):
        client = self._client()
        client.set_api_key('super-secret')
        self.assertEqual(client.session.headers.get('Authorization'), 'Bearer super-secret')

    def test_clearing_key_removes_header(self):
        client = self._client()
        client.set_api_key('abc123')
        client.set_api_key('')
        self.assertNotIn('Authorization', client.session.headers)

    def test_user_url_override_does_not_leak_global_key(self):
        original = lc.db
        lc.db = FakeRuntimeDB(
            ai_rows=[
                _ai_row('api_url', 'http://global:1234/v1'),
                _ai_row('api_key', 'GLOBALKEY'),
            ],
            user_row={'ai_api_url': 'http://user-only:9999/v1', 'ai_api_key': None},
        )
        try:
            client = lc.LMStudioClient(user_id=5)
        finally:
            lc.db = original
        self.assertEqual(client.api_url, 'http://user-only:9999/v1')
        # Global key kullanıcının sunucusuna ASLA gönderilmemeli
        self.assertEqual(client.api_key, '')
        self.assertNotIn('Authorization', client.session.headers)

    def test_user_key_used_with_user_url(self):
        original = lc.db
        lc.db = FakeRuntimeDB(
            ai_rows=[_ai_row('api_key', 'GLOBALKEY')],
            user_row={'ai_api_url': 'http://user-only:9999/v1', 'ai_api_key': 'USERKEY'},
        )
        try:
            client = lc.LMStudioClient(user_id=5)
        finally:
            lc.db = original
        self.assertEqual(client.api_key, 'USERKEY')
        self.assertEqual(client.session.headers.get('Authorization'), 'Bearer USERKEY')


class TestEmbeddingConfigResolution(unittest.TestCase):
    """_resolve_embedding_config kuralları (rag_index)."""

    BASE_CFG = {
        'provider': 'lmstudio',
        'api_url': 'http://chat:1234/v1',
        'api_key': 'CHATKEY',
        'embedding_api_url': '',
        'embedding_model': 'emb-a',
        'embedding_api_key': '',
    }

    def setUp(self):
        original_cache = dict(ri._RUNTIME_SETTINGS_CACHE)
        ri._RUNTIME_SETTINGS_CACHE['value'] = dict(self.BASE_CFG)
        ri._RUNTIME_SETTINGS_CACHE['expires_at'] = time.time() + 60

        def _restore():
            ri._RUNTIME_SETTINGS_CACHE.clear()
            ri._RUNTIME_SETTINGS_CACHE.update(original_cache)
        self.addCleanup(_restore)

    def test_same_server_falls_back_to_chat_key(self):
        cfg = ri._resolve_embedding_config()
        self.assertEqual(cfg['api_url'], 'http://chat:1234/v1')
        self.assertEqual(cfg['model'], 'emb-a')
        self.assertEqual(cfg['api_key'], 'CHATKEY')

    def test_separate_server_does_not_leak_chat_key(self):
        cfg = ri._resolve_embedding_config({'embedding_api_url': 'http://emb:8080/v1'})
        self.assertEqual(cfg['api_url'], 'http://emb:8080/v1')
        self.assertEqual(cfg['api_key'], '')

    def test_embedding_specific_key_wins(self):
        cfg = ri._resolve_embedding_config({
            'embedding_api_url': 'http://emb:8080/v1',
            'embedding_api_key': 'EMBKEY',
        })
        self.assertEqual(cfg['api_key'], 'EMBKEY')

    def test_stored_embedding_key_used_when_no_override(self):
        ri._RUNTIME_SETTINGS_CACHE['value'] = dict(self.BASE_CFG, embedding_api_key='STORED-EMB')
        cfg = ri._resolve_embedding_config()
        self.assertEqual(cfg['api_key'], 'STORED-EMB')

    def test_model_override(self):
        cfg = ri._resolve_embedding_config({'embedding_model': 'other-model'})
        self.assertEqual(cfg['model'], 'other-model')

    def test_embedding_headers_include_bearer_only_with_key(self):
        with_key = ri._embedding_headers('K1')
        self.assertEqual(with_key['Authorization'], 'Bearer K1')
        without_key = ri._embedding_headers('')
        self.assertNotIn('Authorization', without_key)


class TestSensitiveSettingsSemantics(unittest.TestCase):
    """PUT /api/ai-settings/<key> masked/empty/clear davranışı."""

    def setUp(self):
        app.config['TESTING'] = True
        self.client = app.test_client()
        self.original_db = ai_settings_route.db
        self.fake_db = FakeAISettingsDB()
        ai_settings_route.db = self.fake_db
        self.addCleanup(lambda: setattr(ai_settings_route, 'db', self.original_db))

    def test_mask_on_get_helper(self):
        self.assertEqual(ai_settings_route._mask_secret(''), '')
        self.assertEqual(ai_settings_route._mask_secret('abcdefgh1234'), '••••1234')

    def test_new_key_value_is_saved(self):
        resp = self.client.put('/api/ai-settings/api_key',
                               json={'value': 'new-secret-key', 'type': 'string'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(self.fake_db.updates), 1)
        self.assertIn('new-secret-key', self.fake_db.updates[0])

    def test_masked_echo_is_not_saved(self):
        resp = self.client.put('/api/ai-settings/api_key',
                               json={'value': '••••1234', 'type': 'string'})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('unchanged', resp.get_json()['message'])
        self.assertEqual(self.fake_db.updates, [])

    def test_empty_value_without_clear_is_not_saved(self):
        resp = self.client.put('/api/ai-settings/api_key',
                               json={'value': '', 'type': 'string'})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('unchanged', resp.get_json()['message'])
        self.assertEqual(self.fake_db.updates, [])

    def test_empty_value_with_clear_flag_is_saved(self):
        resp = self.client.put('/api/ai-settings/api_key',
                               json={'value': '', 'type': 'string', 'clear': True})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(self.fake_db.updates), 1)
        self.assertIn('', self.fake_db.updates[0])

    def test_non_sensitive_empty_value_is_saved(self):
        # embedding_api_url sensitif değil: boş değer anlamlıdır ("aynı sunucu")
        resp = self.client.put('/api/ai-settings/embedding_api_url',
                               json={'value': '', 'type': 'string'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(self.fake_db.updates), 1)


if __name__ == '__main__':
    unittest.main()
