"""GELIS25 testleri: LLM hata ayrıştırma ve rate-limit bekleme (cooldown).

Gerçek ağ ve veritabanı kullanılmaz; sahte yanıt nesneleriyle çalışır.
"""
import time
import unittest
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from unittest.mock import patch

import backend.lmstudio_client as lc
from backend.llm_errors import (
    CooldownRegistry,
    RateLimitCooldownError,
    cooldown_registry,
    detect_rate_limit,
    extract_error_detail,
    parse_retry_after,
)


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text='', headers=None):
        self.status_code = status_code
        self._payload = payload
        self.text = text
        self.headers = headers or {}

    def json(self):
        if self._payload is None:
            raise ValueError('no json payload')
        return self._payload


class ErrorDetailTests(unittest.TestCase):
    def test_openai_error_message(self):
        response = FakeResponse(429, {
            'error': {
                'message': 'Rate limit reached for requests',
                'type': 'requests',
                'code': 'rate_limit_exceeded',
            }
        })
        detail = extract_error_detail(response)
        self.assertIn('Rate limit reached for requests', detail)
        self.assertIn('type=requests', detail)
        self.assertIn('code=rate_limit_exceeded', detail)

    def test_litellm_error_string(self):
        response = FakeResponse(400, {'error': 'Invalid model name passed in'})
        self.assertEqual(extract_error_detail(response), 'Invalid model name passed in')

    def test_fastapi_detail_list(self):
        response = FakeResponse(422, {
            'detail': [
                {'msg': 'field required', 'loc': ['body', 'model']},
                {'msg': 'invalid value'},
            ]
        })
        detail = extract_error_detail(response)
        self.assertIn('field required', detail)
        self.assertIn('invalid value', detail)

    def test_plain_text_body(self):
        response = FakeResponse(503, text='upstream connect error')
        self.assertEqual(extract_error_detail(response), 'upstream connect error')

    def test_empty_body_falls_back_to_status(self):
        response = FakeResponse(500, text='')
        self.assertEqual(extract_error_detail(response), 'HTTP 500')

    def test_detail_is_truncated(self):
        response = FakeResponse(400, {'error': 'x' * 2000})
        detail = extract_error_detail(response, max_length=50)
        self.assertEqual(len(detail), 51)  # 50 karakter + ellipsis
        self.assertTrue(detail.endswith('…'))


class RetryAfterTests(unittest.TestCase):
    def test_header_seconds(self):
        response = FakeResponse(429, headers={'Retry-After': '30'})
        self.assertEqual(parse_retry_after(response), 30.0)

    def test_header_http_date(self):
        target = datetime.now(timezone.utc) + timedelta(seconds=45)
        response = FakeResponse(429, headers={'Retry-After': format_datetime(target, usegmt=True)})
        seconds = parse_retry_after(response)
        self.assertIsNotNone(seconds)
        self.assertGreater(seconds, 30)
        self.assertLessEqual(seconds, 46)

    def test_body_try_again_in_seconds(self):
        response = FakeResponse(429, text='Rate limit reached. Please try again in 20s.')
        self.assertEqual(parse_retry_after(response), 20.0)

    def test_body_try_again_in_milliseconds(self):
        response = FakeResponse(429, text='Please try again in 1500ms.')
        self.assertAlmostEqual(parse_retry_after(response), 1.5)

    def test_body_retry_after_json(self):
        response = FakeResponse(429, {'error': {'message': 'quota'}, 'retry_after': 12})
        self.assertEqual(parse_retry_after(response), 12.0)

    def test_no_hint_returns_none(self):
        response = FakeResponse(429, text='Too many requests')
        self.assertIsNone(parse_retry_after(response))


class DetectRateLimitTests(unittest.TestCase):
    def test_429_is_always_rate_limit(self):
        self.assertTrue(detect_rate_limit(FakeResponse(429, text='')))

    def test_500_is_never_rate_limit(self):
        self.assertFalse(detect_rate_limit(FakeResponse(500, text='rate limit exceeded')))

    def test_400_with_quota_keyword(self):
        response = FakeResponse(400, {'error': {'message': 'insufficient_quota'}})
        self.assertTrue(detect_rate_limit(response))

    def test_400_generic_error_is_not_rate_limit(self):
        response = FakeResponse(400, {'error': {'message': 'invalid model'}})
        self.assertFalse(detect_rate_limit(response))

    def test_success_is_not_rate_limit(self):
        self.assertFalse(detect_rate_limit(FakeResponse(200, {'data': []})))


class CooldownRegistryTests(unittest.TestCase):
    def setUp(self):
        self.registry = CooldownRegistry()

    def test_set_and_remaining(self):
        self.registry.set('http://server/v1', 5, 'quota')
        remaining = self.registry.remaining('http://server/v1')
        self.assertGreater(remaining, 4)
        self.assertLessEqual(remaining, 5)
        self.assertEqual(self.registry.reason('http://server/v1'), 'quota')

    def test_set_does_not_shorten_existing(self):
        self.registry.set('key', 10)
        self.registry.set('key', 2)
        self.assertGreater(self.registry.remaining('key'), 9)

    def test_set_extends_existing(self):
        self.registry.set('key', 2)
        self.registry.set('key', 10)
        self.assertGreater(self.registry.remaining('key'), 9)

    def test_wait_sleeps_when_within_limit(self):
        self.registry.set('key', 0.05)
        started = time.monotonic()
        remaining = self.registry.wait('key', max_wait=1)
        elapsed = time.monotonic() - started
        self.assertEqual(remaining, 0.0)
        self.assertGreaterEqual(elapsed, 0.04)

    def test_wait_returns_remaining_when_too_long(self):
        self.registry.set('key', 30)
        started = time.monotonic()
        remaining = self.registry.wait('key', max_wait=1)
        elapsed = time.monotonic() - started
        self.assertGreater(remaining, 25)
        self.assertLess(elapsed, 0.5)

    def test_clear_single_key(self):
        self.registry.set('a', 10)
        self.registry.set('b', 10)
        self.registry.clear('a')
        self.assertEqual(self.registry.remaining('a'), 0.0)
        self.assertGreater(self.registry.remaining('b'), 0)

    def test_clear_all(self):
        self.registry.set('a', 10)
        self.registry.set('b', 10)
        self.registry.clear()
        self.assertEqual(self.registry.remaining('a'), 0.0)
        self.assertEqual(self.registry.remaining('b'), 0.0)

    def test_expired_entry_is_removed(self):
        self.registry.set('key', 0.01)
        time.sleep(0.02)
        self.assertEqual(self.registry.remaining('key'), 0.0)
        self.assertIsNone(self.registry.reason('key'))


class RateLimitCooldownErrorTests(unittest.TestCase):
    def test_attributes(self):
        error = RateLimitCooldownError('bekle', 12.5)
        self.assertEqual(str(error), 'bekle')
        self.assertEqual(error.retry_after_seconds, 12.5)


class ClientIntegrationTests(unittest.TestCase):
    def setUp(self):
        cooldown_registry.clear()
        # DB/ağ bağımlılığı olmadan yalnız gerekli alanları kur.
        self.client = object.__new__(lc.LMStudioClient)
        self.client.api_url = 'http://test-server:4001/v1'
        self.client.provider = 'vllm'

    def tearDown(self):
        cooldown_registry.clear()

    def test_register_rate_limit_uses_retry_after(self):
        response = FakeResponse(429, {'error': {'message': 'quota'}}, headers={'Retry-After': '7'})
        seconds = self.client._register_rate_limit(response)
        self.assertEqual(seconds, 7.0)
        self.assertGreater(self.client.rate_limit_remaining(), 6)

    def test_register_rate_limit_defaults_without_hint(self):
        response = FakeResponse(429, {'error': {'message': 'too many requests'}})
        with patch.object(lc, 'LLM_RATE_LIMIT_COOLDOWN', 42):
            seconds = self.client._register_rate_limit(response)
        self.assertEqual(seconds, 42.0)

    def test_register_ignores_non_rate_limit(self):
        response = FakeResponse(400, {'error': {'message': 'invalid model'}})
        self.assertIsNone(self.client._register_rate_limit(response))
        self.assertEqual(self.client.rate_limit_remaining(), 0.0)

    def test_ensure_not_rate_limited_raises_when_too_long(self):
        cooldown_registry.set(self.client._cooldown_key(), 60, 'quota')
        with patch.object(lc, 'LLM_RATE_LIMIT_MAX_WAIT', 1):
            with self.assertRaises(RateLimitCooldownError) as ctx:
                self.client._ensure_not_rate_limited()
        self.assertGreater(ctx.exception.retry_after_seconds, 50)
        self.assertIn('quota', str(ctx.exception))

    def test_ensure_not_rate_limited_waits_when_short(self):
        cooldown_registry.set(self.client._cooldown_key(), 0.05)
        with patch.object(lc, 'LLM_RATE_LIMIT_MAX_WAIT', 1):
            self.client._ensure_not_rate_limited()
        self.assertEqual(self.client.rate_limit_remaining(), 0.0)

    def test_http_error_message_includes_detail_and_hint(self):
        response = FakeResponse(429, {'error': {'message': 'quota exceeded'}})
        message = self.client._http_error_message(response, retry_after=9)
        self.assertIn('vLLM HTTP 429', message)
        self.assertIn('quota exceeded', message)
        self.assertIn('9 saniye', message)


if __name__ == '__main__':
    unittest.main()
