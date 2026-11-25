"""LLM hata ayrıştırma ve rate-limit bekleme (cooldown) yardımcıları.

OpenAI uyumlu sunucular (OpenAI, vLLM, LiteLLM, LM Studio, llama.cpp) hata
gövdelerini farklı biçimlerde döndürür. Bu modül:

* ``extract_error_detail`` ile gövdeden okunabilir bir hata mesajı çıkarır,
* ``parse_retry_after`` ile ``Retry-After`` başlığını veya gövdedeki
  "try again in 20s" benzeri ipuçlarını saniyeye çevirir,
* ``detect_rate_limit`` ile yanıtın rate-limit/kota hatası olup olmadığını
  belirler,
* ``CooldownRegistry`` ile süreç genelinde thread-safe bir bekleme kaydı tutar.

Böylece bir istek 429 aldığında sonraki LLM istekleri hemen sunucuya
yüklenmez; süre dolana kadar bekler veya kalan süreyi bildirir.
"""
from __future__ import annotations

import json
import re
import threading
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

# Rate-limit olduğu düşünülen gövde ifadeleri (küçük harfle karşılaştırılır).
_RATE_LIMIT_KEYWORDS = (
    'rate limit',
    'rate_limit',
    'ratelimit',
    'too many requests',
    'quota exceeded',
    'quota_exceeded',
    'insufficient_quota',
    'resource_exhausted',
    'resource exhausted',
    'overloaded',
    'requests per minute',
    'tokens per minute',
    'request rate',
)

# "try again in 20s", "retry after 30", "retry_after": 20 gibi ipuçları.
_RETRY_HINT_PATTERNS = (
    re.compile(
        r'try\s+again\s+in\s+([0-9]+(?:\.[0-9]+)?)\s*'
        r'(ms|milliseconds?|s|secs?|seconds?|m|mins?|minutes?)?',
        re.IGNORECASE,
    ),
    re.compile(
        r'retry\s+after\s+([0-9]+(?:\.[0-9]+)?)\s*'
        r'(ms|milliseconds?|s|secs?|seconds?|m|mins?|minutes?)?',
        re.IGNORECASE,
    ),
    re.compile(
        r'(?:wait|available|reset)\s+(?:for\s+)?([0-9]+(?:\.[0-9]+)?)\s*'
        r'(ms|milliseconds?|s|secs?|seconds?|m|mins?|minutes?)',
        re.IGNORECASE,
    ),
    re.compile(
        r'"retry_after(?:_seconds)?"\s*:\s*"?([0-9]+(?:\.[0-9]+)?)"?',
        re.IGNORECASE,
    ),
    re.compile(
        r'"retryDelay"\s*:\s*"([0-9]+(?:\.[0-9]+)?)\s*(ms|s|m)?"',
        re.IGNORECASE,
    ),
)


class RateLimitCooldownError(RuntimeError):
    """Aktif rate-limit beklemesi nedeniyle istek gönderilmedi."""

    def __init__(self, message: str, retry_after_seconds: float):
        super().__init__(message)
        self.retry_after_seconds = float(retry_after_seconds)


def _response_text(response) -> str:
    """Yanıt gövdesini metin olarak döndür (okunamazsa boş string)."""
    try:
        text = response.text
    except Exception:
        text = ''
    if text:
        return text
    try:
        payload = response.json()
    except Exception:
        return ''
    try:
        return json.dumps(payload, ensure_ascii=False)
    except Exception:
        return str(payload)


def _json_payload(response):
    try:
        return response.json()
    except Exception:
        return None


def _unit_to_seconds(value: float, unit: str | None) -> float:
    unit = (unit or 's').lower()
    if unit.startswith('ms') or unit.startswith('millisecond'):
        return value / 1000.0
    if unit.startswith('m') and not unit.startswith('ms'):
        return value * 60.0
    return value


def parse_retry_after(response) -> float | None:
    """``Retry-After`` başlığını veya gövde ipucunu saniye olarak döndür.

    Desteklenen biçimler:
    * ``Retry-After: 30`` (saniye)
    * ``Retry-After: Wed, 21 Oct 2015 07:28:00 GMT`` (HTTP-date)
    * Gövdede ``try again in 20s`` / ``retry after 30`` / ``"retry_after": 20``
    """
    headers = getattr(response, 'headers', None) or {}
    raw_header = headers.get('Retry-After') or headers.get('retry-after')
    if raw_header:
        raw_header = str(raw_header).strip()
        try:
            seconds = float(raw_header)
            if seconds >= 0:
                return seconds
        except (TypeError, ValueError):
            pass
        try:
            target = parsedate_to_datetime(raw_header)
            if target.tzinfo is None:
                target = target.replace(tzinfo=timezone.utc)
            seconds = (target - datetime.now(timezone.utc)).total_seconds()
            if seconds > 0:
                return seconds
        except (TypeError, ValueError, OverflowError):
            pass

    text = _response_text(response)
    if not text:
        return None

    for pattern in _RETRY_HINT_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        try:
            value = float(match.group(1))
        except (TypeError, ValueError):
            continue
        unit = match.group(2) if match.lastindex and match.lastindex >= 2 else None
        seconds = _unit_to_seconds(value, unit)
        if seconds >= 0:
            return seconds
    return None


def detect_rate_limit(response) -> bool:
    """Yanıt rate-limit/kota hatası mı?

    429 her zaman rate-limit sayılır. 500 sunucu hatası rate-limit sayılmaz;
    diğer durum kodlarında yalnızca gövde belirgin bir rate-limit ifadesi
    içeriyorsa True döner.
    """
    status = getattr(response, 'status_code', None)
    if status == 429:
        return True
    if status == 500:
        return False
    if isinstance(status, int) and 200 <= status < 300:
        return False

    text = _response_text(response).lower()
    if not text:
        return False
    return any(keyword in text for keyword in _RATE_LIMIT_KEYWORDS)


def extract_error_detail(response, max_length: int = 1000) -> str:
    """Yanıt gövdesinden okunabilir, ayrıntılı hata mesajı çıkar.

    OpenAI (``error.message``), vLLM (``message``/``type``), FastAPI
    (``detail``) ve LiteLLM (``error``/``detail``) biçimlerini destekler.
    Gövde çözümlenemezse ham metne düşer.
    """
    payload = _json_payload(response)
    parts: list[str] = []

    if isinstance(payload, dict):
        error = payload.get('error')
        if isinstance(error, dict):
            message = error.get('message') or error.get('msg')
            if message:
                parts.append(str(message).strip())
            meta = []
            for key in ('type', 'code', 'param'):
                value = error.get(key)
                if value not in (None, '', 0):
                    meta.append(f'{key}={value}')
            if meta:
                parts.append('(' + ', '.join(meta) + ')')
        elif isinstance(error, str) and error.strip():
            parts.append(error.strip())

        if not parts:
            for key in ('message', 'msg', 'detail', 'error_description'):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    parts.append(value.strip())
                    break
                if isinstance(value, list):
                    messages = []
                    for item in value:
                        if isinstance(item, dict):
                            item_message = item.get('msg') or item.get('message')
                            if item_message:
                                messages.append(str(item_message))
                        elif isinstance(item, str) and item.strip():
                            messages.append(item.strip())
                    if messages:
                        parts.append('; '.join(messages))
                        break

            meta = []
            for key in ('type', 'code'):
                value = payload.get(key)
                if value not in (None, '') and not isinstance(value, (dict, list)):
                    meta.append(f'{key}={value}')
            if meta:
                parts.append('(' + ', '.join(meta) + ')')

    if not parts:
        text = _response_text(response).strip()
        if text:
            parts.append(text)

    detail = ' '.join(part for part in parts if part).strip()
    if not detail:
        status = getattr(response, 'status_code', None)
        detail = f'HTTP {status}' if status else 'Bilinmeyen hata'
    if len(detail) > max_length:
        detail = detail[:max_length].rstrip() + '…'
    return detail


class CooldownRegistry:
    """Süreç genelinde thread-safe rate-limit bekleme kaydı.

    Anahtar genellikle sunucu URL'sidir; aynı sunucuya giden tüm istekler
    (farklı kullanıcılar dahil) aynı kotayı paylaştığı için bekleme paylaşılır.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._deadlines: dict[str, float] = {}
        self._reasons: dict[str, str] = {}

    def set(self, key: str, seconds: float, reason: str | None = None) -> float:
        """Bekleme süresini ayarla; mevcut daha uzun süreyi kısaltma."""
        try:
            seconds = float(seconds)
        except (TypeError, ValueError):
            seconds = 0.0
        seconds = max(0.0, seconds)
        with self._lock:
            deadline = time.monotonic() + seconds
            if deadline > self._deadlines.get(key, 0.0):
                self._deadlines[key] = deadline
                if reason:
                    self._reasons[key] = reason
            return seconds

    def remaining(self, key: str) -> float:
        """Kalan bekleme süresini saniye olarak döndür (yoksa 0)."""
        with self._lock:
            deadline = self._deadlines.get(key)
            if not deadline:
                return 0.0
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                self._deadlines.pop(key, None)
                self._reasons.pop(key, None)
                return 0.0
            return remaining

    def reason(self, key: str) -> str | None:
        with self._lock:
            return self._reasons.get(key)

    def clear(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._deadlines.clear()
                self._reasons.clear()
            else:
                self._deadlines.pop(key, None)
                self._reasons.pop(key, None)

    def wait(self, key: str, max_wait: float) -> float:
        """Beklemeyi uygula ve kalan süreyi döndür.

        Kalan süre ``max_wait`` içindeyse uyur ve 0 döndürür. Daha uzunsa
        hiç uyumadan kalan süreyi döndürür; çağıran isteği göndermemelidir.
        """
        remaining = self.remaining(key)
        if remaining <= 0:
            return 0.0
        try:
            max_wait = float(max_wait)
        except (TypeError, ValueError):
            max_wait = 0.0
        if remaining > max_wait:
            return remaining
        time.sleep(remaining)
        return self.remaining(key)


# Tüm LLM istemcileri tarafından paylaşılan kayıt.
cooldown_registry = CooldownRegistry()
