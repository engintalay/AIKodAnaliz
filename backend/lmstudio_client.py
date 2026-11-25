import os
import math
import requests
import json
import time
from config.config import (
    LMSTUDIO_API_URL,
    LMSTUDIO_DEFAULT_MODEL,
    LMSTUDIO_MAX_TOKENS,
    LMSTUDIO_TEMPERATURE,
    LMSTUDIO_TOP_P,
    LMSTUDIO_REQUEST_TIMEOUT,
    CONTEXT_LIMIT_TOKENS,
    AI_API_KEY,
    LLM_RATE_LIMIT_COOLDOWN,
    LLM_RATE_LIMIT_MAX_WAIT,
)
from backend.database import db
from backend.llm_errors import (
    RateLimitCooldownError,
    cooldown_registry,
    detect_rate_limit,
    extract_error_detail,
    parse_retry_after,
)

class LMStudioClient:
    """Client for OpenAI-compatible local AI servers (LMStudio, llama.cpp)."""
    
    def __init__(self, user_id=None):
        self.provider = 'lmstudio'
        self.api_url = LMSTUDIO_API_URL
        self.api_key = AI_API_KEY
        self.model = LMSTUDIO_DEFAULT_MODEL
        self.max_tokens = LMSTUDIO_MAX_TOKENS
        self.temperature = LMSTUDIO_TEMPERATURE
        self.top_p = LMSTUDIO_TOP_P
        self.context_limit = CONTEXT_LIMIT_TOKENS
        # Local models can have long load and inference delays.
        # Default is 15 minutes and can be overridden from env/DB settings.
        self.request_timeout = LMSTUDIO_REQUEST_TIMEOUT
        self.retry_count = 3

        # Load runtime overrides from ai_settings table (if present)
        self._load_runtime_settings(user_id)

        # Never inherit OS/env proxy settings.
        self.session = requests.Session()
        self.session.trust_env = False
        self._apply_auth_header()
        self.last_call_stats = {
            'duration_seconds': 0.0,
            'prompt_tokens': 0,
            'completion_tokens': 0,
            'total_tokens': 0,
        }

    def _apply_auth_header(self):
        """Set (or clear) the Authorization header once for the whole session.

        All chat/embedding/model-list calls share this session, so the API key
        only needs to be wired here — never at individual call sites.
        """
        if self.api_key:
            self.session.headers['Authorization'] = f'Bearer {self.api_key}'
        else:
            self.session.headers.pop('Authorization', None)

    def set_api_key(self, api_key):
        """Override API key at runtime (used by connection-test flows; not persisted)."""
        self.api_key = (api_key or '').strip()
        self._apply_auth_header()

    @property
    def provider_display(self) -> str:
        mapping = {
            'lmstudio': 'LMStudio',
            'llamacpp': 'llama.cpp',
            'vllm': 'vLLM',
            'openai': 'OpenAI',
        }
        return mapping.get((self.provider or '').lower(), self.provider or 'AI Server')

    def _load_runtime_settings(self, user_id=None):
        """Load dynamic AI settings from database with safe fallbacks."""
        try:
            rows = db.execute_query('SELECT setting_name, setting_value, data_type FROM ai_settings')
            for row in rows:
                name = row['setting_name']
                value = row['setting_value']
                data_type = row['data_type']

                if data_type == 'integer':
                    parsed = int(value)
                elif data_type == 'float':
                    parsed = float(value)
                elif data_type == 'boolean':
                    parsed = str(value).lower() == 'true'
                else:
                    parsed = value

                if name == 'api_url' and parsed:
                    self.api_url = str(parsed).strip().rstrip('/')
                elif name == 'api_key':
                    self.api_key = str(parsed or '').strip()
                elif name == 'provider' and parsed:
                    self.provider = str(parsed).strip().lower()
                elif name == 'model_name' and parsed:
                    self.model = str(parsed).strip()
                elif name == 'max_tokens':
                    self.max_tokens = int(parsed)
                elif name == 'temperature':
                    self.temperature = float(parsed)
                elif name == 'top_p':
                    self.top_p = float(parsed)
                elif name == 'timeout':
                    self.request_timeout = int(parsed)
                elif name == 'retry_count':
                    self.retry_count = int(parsed)
                elif name == 'context_limit':
                    self.context_limit = int(parsed)

            # Per-user override for AI server URL (and matching key)
            if user_id is not None:
                user_rows = db.execute_query(
                    'SELECT ai_api_url, ai_api_key, ai_model FROM user_settings WHERE user_id = ?',
                    [user_id]
                )
                if user_rows:
                    user_row = dict(user_rows[0])
                    user_api_url = (user_row.get('ai_api_url') or '').strip()
                    user_api_key = (user_row.get('ai_api_key') or '').strip()
                    user_model = (user_row.get('ai_model') or '').strip()
                    if user_api_url:
                        self.api_url = user_api_url.rstrip('/')
                        # Kullanıcı kendi sunucusuna yönlenmişse global anahtar
                        # ASLA o sunucuya gönderilmez; yalnız kullanıcı anahtarı.
                        self.api_key = user_api_key
                    if user_model:
                        self.model = user_model
        except Exception:
            # Keep config defaults if DB is unavailable or malformed.
            pass

    def _is_invalid_model_response(self, response) -> bool:
        """Detect remote provider invalid model errors from HTTP response."""
        if response.status_code != 400:
            return False
        try:
            payload = response.json()
            text = json.dumps(payload, ensure_ascii=False).lower()
        except Exception:
            text = (response.text or '').lower()
        return ('invalid model' in text) or ('invalid model identifier' in text)

    # ------------------------------------------------------------------
    # Rate limit / hata yardımcıları
    # ------------------------------------------------------------------
    def _cooldown_key(self) -> str:
        """Bekleme kaydının anahtarı: aynı sunucuya giden istekler paylaşır."""
        return (self.api_url or '').rstrip('/')

    def rate_limit_remaining(self) -> float:
        """Aktif rate-limit beklemesinden kalan saniye (yoksa 0)."""
        return cooldown_registry.remaining(self._cooldown_key())

    def wait_for_rate_limit(self) -> float:
        """Beklemeyi uygula; hâlâ bekleme gerekiyorsa kalan saniyeyi döndür."""
        return cooldown_registry.wait(self._cooldown_key(), LLM_RATE_LIMIT_MAX_WAIT)

    def _ensure_not_rate_limited(self):
        """Aktif bekleme varsa uygula; üst sınırı aşıyorsa isteği engelle."""
        remaining = self.wait_for_rate_limit()
        if remaining <= 0:
            return
        reason = cooldown_registry.reason(self._cooldown_key())
        message = (
            f"{self.provider_display} rate limit aktif; yaklaşık "
            f"{int(math.ceil(remaining))} saniye sonra tekrar deneyin."
        )
        if reason:
            message += f" Sunucu mesajı: {reason}"
        raise RateLimitCooldownError(message, remaining)

    def _register_rate_limit(self, response):
        """Yanıt rate-limit ise süreç geneli bekleme kaydını güncelle."""
        if not detect_rate_limit(response):
            return None
        seconds = parse_retry_after(response)
        if seconds is None:
            seconds = LLM_RATE_LIMIT_COOLDOWN
        try:
            seconds = float(seconds)
        except (TypeError, ValueError):
            seconds = float(LLM_RATE_LIMIT_COOLDOWN)
        # Çok kısa/çok uzun değerleri makul aralığa sıkıştır.
        seconds = max(1.0, min(seconds, 3600.0))
        cooldown_registry.set(
            self._cooldown_key(), seconds, extract_error_detail(response)
        )
        return seconds

    def _http_error_message(self, response, retry_after=None) -> str:
        """Ayrıntılı HTTP hata metni (rate-limit ipucu dahil)."""
        detail = extract_error_detail(response)
        message = f"{self.provider_display} HTTP {response.status_code}: {detail}"
        if retry_after:
            message += (
                f" — rate limit; yaklaşık {int(math.ceil(retry_after))} "
                "saniye sonra tekrar deneyin."
            )
        return message

    @staticmethod
    def _normalize_messages(messages):
        """System mesajlarını başa topla ve tek mesajda birleştir.

        Bazı chat template'leri (ör. LiteLLM arkasındaki Ornith/Qwen
        varyantları) birden fazla system mesajını veya ilk sırada olmayan
        system mesajını reddeder: "System message must be at the beginning."
        Bu yardımcı, tüm system içeriklerini sırayı koruyarak tek bir baştaki
        mesajda birleştirir; diğer mesajların sırasını değiştirmez.
        """
        system_parts = []
        rest = []
        for message in messages or []:
            if not isinstance(message, dict):
                continue
            if message.get("role") == "system":
                content = message.get("content")
                if isinstance(content, str):
                    if content.strip():
                        system_parts.append(content.strip())
                elif content:
                    system_parts.append(str(content))
                continue
            rest.append(message)

        normalized = []
        if system_parts:
            normalized.append({"role": "system", "content": "\n\n".join(system_parts)})
        normalized.extend(rest)
        return normalized

    @staticmethod
    def _extract_message_text(data):
        """Asistan metnini döndür; reasoning-only modellerde content boş olabilir."""
        try:
            message = data['choices'][0]['message']
        except (KeyError, IndexError, TypeError):
            return ''
        content = message.get('content')
        if content is None:
            content = message.get('reasoning_content') or message.get('reasoning') or ''
        return str(content).strip()

    def _build_chat_payload(self, prompt, temperature, top_p, max_tokens):
        return {
            "model": self.model,
            "messages": self._normalize_messages([
                {
                    "role": "system",
                    "content": "Yanıt dili zorunlu olarak Türkçe olmalı. İngilizce veya başka dil kullanma."
                },
                {
                    "role": "system",
                    "content": "Olabildiğince detaylı ve açıklayıcı ol. Teknik detaylara girmekten çekinme. Kodun ne yaptığını, nasıl çalıştığını, neden öyle yapıldığını anlat. Eğer kodda belirsizlikler varsa, mümkün olan en iyi tahminini yaparak bunları da açıklamaya çalış. Eğer kodun amacı veya işlevi hakkında kesin bir fikrin yoksa, bunu açıkça belirt ve olası senaryoları sıralayarak açıklamaya çalış. Kodun hangi problemleri çözmeye çalıştığını, hangi ihtiyaçlara hizmet ettiğini, hangi durumlarda kullanışlı olabileceğini anlat. Kodun güçlü ve zayıf yönlerini, potansiyel riskleri veya yan etkileri varsa bunları da açıklamaya çalış. Kodun nasıl geliştirilebileceği veya iyileştirilebileceği konusunda önerilerin varsa bunları da paylaş. Kodun genel bağlamını, kullanım senaryolarını ve teknik detaylarını mümkün olan en iyi şekilde açıklamaya çalış.  "
                },
                {"role": "user", "content": prompt}
            ]),
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
            "stream": False
        }

    def _post_chat_with_model_fallback(self, prompt, temperature, top_p, max_tokens):
        """Send chat request; if model is invalid, auto-pick first available model and retry once."""
        self._ensure_not_rate_limited()
        response = self.session.post(
            f"{self.api_url}/chat/completions",
            headers={"Content-Type": "application/json"},
            json=self._build_chat_payload(prompt, temperature, top_p, max_tokens),
            timeout=self.request_timeout
        )
        self._register_rate_limit(response)

        if self._is_invalid_model_response(response):
            try:
                models = self.list_models()
                if models:
                    self.model = models[0]
                    response = self.session.post(
                        f"{self.api_url}/chat/completions",
                        headers={"Content-Type": "application/json"},
                        json=self._build_chat_payload(prompt, temperature, top_p, max_tokens),
                        timeout=self.request_timeout
                    )
                    self._register_rate_limit(response)
            except Exception:
                # Keep original response if model list/retry fails.
                pass

        return response

    def list_models(self) -> list:
        """Return model IDs from OpenAI-compatible /models endpoint."""
        self._ensure_not_rate_limited()
        response = self.session.get(f"{self.api_url}/models", timeout=10)
        retry_after = self._register_rate_limit(response)
        if response.status_code != 200:
            raise RuntimeError(self._http_error_message(response, retry_after))
        payload = response.json()
        models = payload.get('data', []) if isinstance(payload, dict) else []
        model_ids = []
        for model in models:
            model_id = model.get('id') if isinstance(model, dict) else None
            if model_id:
                model_ids.append(model_id)
        return model_ids

    def _base_url(self) -> str:
        """Server base URL without the OpenAI-compatible ``/v1`` suffix."""
        url = (self.api_url or '').rstrip('/')
        if url.endswith('/v1'):
            return url[:-3]
        return url

    @staticmethod
    def _first_int(payload: dict, *keys):
        """Return the first positive integer found under any of ``keys``."""
        for key in keys:
            value = payload.get(key)
            if value is None:
                continue
            try:
                parsed = int(value)
            except (TypeError, ValueError):
                continue
            if parsed > 0:
                return parsed
        return None

    def _enrich_models_lmstudio(self, models: list):
        """Add LM Studio native metadata (context length, state, quantization)."""
        try:
            response = self.session.get(f"{self._base_url()}/api/v0/models", timeout=5)
            if response.status_code != 200:
                return
            payload = response.json()
        except Exception:
            return

        items = payload.get('data', []) if isinstance(payload, dict) else []
        by_id = {model['id']: model for model in models}
        for item in items:
            if not isinstance(item, dict):
                continue
            target = by_id.get(item.get('id'))
            if not target:
                continue
            context_length = self._first_int(item, 'max_context_length', 'loaded_context_length')
            if context_length:
                target['context_length'] = context_length
            for key in ('state', 'type', 'quantization', 'publisher', 'arch'):
                if item.get(key):
                    target[key] = item[key]

    def _enrich_models_llamacpp(self, models: list):
        """Add llama.cpp ``/props`` metadata (context, n_predict, generation defaults)."""
        try:
            response = self.session.get(f"{self._base_url()}/props", timeout=5)
            if response.status_code != 200:
                return
            payload = response.json()
        except Exception:
            return
        if not isinstance(payload, dict):
            return

        generation = payload.get('default_generation_settings') or {}
        if not isinstance(generation, dict):
            generation = {}

        context_length = self._first_int(generation, 'n_ctx')
        max_output = self._first_int(generation, 'n_predict')

        defaults = {}
        for key in ('temperature', 'top_p', 'top_k', 'repeat_penalty'):
            if generation.get(key) is not None:
                defaults[key] = generation[key]
        if max_output:
            defaults['max_tokens'] = max_output

        # llama.cpp normally serves a single model; when several are listed,
        # only attach the props to the model that matches ``model_path``.
        targets = models
        if len(models) > 1:
            model_path = payload.get('model_path') or ''
            basename = os.path.basename(model_path) if model_path else ''
            if basename:
                targets = [
                    model for model in models
                    if model['id'] == basename
                    or basename in model['id']
                    or model['id'] in basename
                ]

        for model in targets:
            if context_length:
                model['context_length'] = context_length
            if max_output:
                model['max_output_tokens'] = max_output
            if defaults:
                model['defaults'] = dict(defaults)

    def list_models_with_metadata(self) -> dict:
        """List models with context/output limits and provider defaults.

        Returns ``{models, api_url, provider, error}``. Never raises: a failed
        request yields an empty list plus an ``error`` string so the UI can
        show a useful message instead of a 500.
        """
        result = {
            'models': [],
            'api_url': self.api_url,
            'provider': self.provider,
            'error': None,
        }
        try:
            self._ensure_not_rate_limited()
            response = self.session.get(f"{self.api_url}/models", timeout=10)
            retry_after = self._register_rate_limit(response)
            if response.status_code != 200:
                result['error'] = self._http_error_message(response, retry_after)
                if retry_after:
                    result['retry_after_seconds'] = retry_after
                return result
            payload = response.json()
        except RateLimitCooldownError as exc:
            result['error'] = str(exc)
            result['retry_after_seconds'] = exc.retry_after_seconds
            return result
        except Exception as exc:
            result['error'] = str(exc)
            return result

        raw_models = payload.get('data', []) if isinstance(payload, dict) else []
        models = []
        for item in raw_models:
            if not isinstance(item, dict) or not item.get('id'):
                continue
            models.append({
                'id': item['id'],
                'context_length': self._first_int(
                    item, 'context_length', 'max_context_length', 'max_model_len',
                    'max_input_tokens'
                ),
                'max_output_tokens': self._first_int(
                    item, 'max_output_tokens', 'max_completion_tokens'
                ),
                'state': item.get('state'),
                'type': item.get('type'),
                'quantization': item.get('quantization'),
                'publisher': item.get('publisher'),
                'arch': item.get('arch'),
                'defaults': None,
            })

        # vLLM/OpenAI uyumlu sunucularda LM Studio (/api/v0/models) ve
        # llama.cpp (/props) uç noktaları yoktur; bu sağlayıcılarda yalnız
        # /v1/models kullanılır. lmstudio/llamacpp için geriye uyumlu olarak
        # iki zenginleştirme de denenir (yanlış etiketlenmiş sunucularda da
        # meta veri kaybolmasın).
        provider = (self.provider or '').strip().lower()
        if provider not in ('vllm', 'openai'):
            self._enrich_models_lmstudio(models)
            self._enrich_models_llamacpp(models)

        for model in models:
            if model.get('max_output_tokens'):
                model['suggested_max_tokens'] = model['max_output_tokens']
            elif model.get('context_length'):
                model['suggested_max_tokens'] = min(model['context_length'], 4096)
            else:
                model['suggested_max_tokens'] = None

        result['models'] = models
        return result

    def test_generation(self, prompt: str = None, max_tokens: int = 256) -> dict:
        """Send a real chat completion and verify that the model answers.

        A ``/models`` connection test only proves the server is reachable; this
        method proves the selected model can actually produce a response.

        Reasoning models (e.g. Qwen3) may spend the whole budget on
        ``reasoning_content`` and return an empty ``content``. Such a response
        still proves the model works, so reasoning text is accepted as a reply.
        """
        prompt = prompt or "Sadece OK yaz."
        try:
            max_tokens = max(1, int(max_tokens or 256))
        except (TypeError, ValueError):
            max_tokens = 256

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "max_tokens": max_tokens,
            "stream": False,
        }

        started_at = time.perf_counter()
        retry_after = None
        try:
            self._ensure_not_rate_limited()
            response = self.session.post(
                f"{self.api_url}/chat/completions",
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=self.request_timeout,
            )
            retry_after = self._register_rate_limit(response)
            if self._is_invalid_model_response(response):
                models = self.list_models()
                if models:
                    self.model = models[0]
                    payload["model"] = self.model
                    response = self.session.post(
                        f"{self.api_url}/chat/completions",
                        headers={"Content-Type": "application/json"},
                        json=payload,
                        timeout=self.request_timeout,
                    )
                    retry_after = self._register_rate_limit(response)
        except RateLimitCooldownError as exc:
            return {
                'status': 'error',
                'model': self.model,
                'latency_ms': int((time.perf_counter() - started_at) * 1000),
                'error': str(exc),
                'retry_after_seconds': exc.retry_after_seconds,
            }
        except requests.exceptions.Timeout:
            return {
                'status': 'error',
                'model': self.model,
                'latency_ms': int((time.perf_counter() - started_at) * 1000),
                'error': f'İstek {self.request_timeout} saniyede zaman aşımına uğradı.',
            }
        except requests.exceptions.ConnectionError:
            return {
                'status': 'error',
                'model': self.model,
                'latency_ms': int((time.perf_counter() - started_at) * 1000),
                'error': f'{self.provider_display} sunucusuna bağlanılamadı ({self.api_url}).',
            }
        except Exception as exc:
            return {
                'status': 'error',
                'model': self.model,
                'latency_ms': int((time.perf_counter() - started_at) * 1000),
                'error': str(exc),
            }

        latency_ms = int((time.perf_counter() - started_at) * 1000)
        if response.status_code != 200:
            error_result = {
                'status': 'error',
                'model': self.model,
                'latency_ms': latency_ms,
                'status_code': response.status_code,
                'error': self._http_error_message(response, retry_after),
            }
            if retry_after:
                error_result['retry_after_seconds'] = retry_after
            return error_result

        try:
            data = response.json()
        except Exception as exc:
            return {
                'status': 'error',
                'model': self.model,
                'latency_ms': latency_ms,
                'error': f'Yanıt JSON olarak çözümlenemedi: {exc}',
            }

        choices = data.get('choices') or []
        message = (choices[0].get('message') or {}) if choices else {}
        content = (message.get('content') or '').strip()
        reasoning = (message.get('reasoning_content') or '').strip()
        reply = content or reasoning
        usage = data.get('usage') or {}

        if not reply:
            finish_reason = choices[0].get('finish_reason') if choices else None
            return {
                'status': 'error',
                'model': self.model,
                'latency_ms': latency_ms,
                'finish_reason': finish_reason,
                'error': 'Model boş yanıt döndürdü (içerik yok).',
            }

        return {
            'status': 'ok',
            'model': self.model,
            'reply': reply,
            'reasoning_only': not content,
            'latency_ms': latency_ms,
            'prompt_tokens': int(usage.get('prompt_tokens', 0) or 0),
            'completion_tokens': int(usage.get('completion_tokens', 0) or 0),
            'total_tokens': int(usage.get('total_tokens', 0) or 0),
        }
    
    def test_connection(self) -> dict:
        """Test connection to active provider endpoint."""
        try:
            self._ensure_not_rate_limited()
            response = self.session.get(f"{self.api_url}/models", timeout=5)
            retry_after = self._register_rate_limit(response)
            if response.status_code == 200:
                return {
                    'status': 'connected',
                    'message': f'Successfully connected to {self.provider_display}',
                    'provider': self.provider,
                }
            else:
                result = {
                    'status': 'error',
                    'message': self._http_error_message(response, retry_after),
                    'provider': self.provider,
                }
                if retry_after:
                    result['retry_after_seconds'] = retry_after
                return result
        except RateLimitCooldownError as exc:
            return {
                'status': 'error',
                'message': str(exc),
                'provider': self.provider,
                'retry_after_seconds': exc.retry_after_seconds,
            }
        except requests.exceptions.ConnectionError:
            return {
                'status': 'error',
                'message': f'Cannot connect to {self.provider_display}. Make sure it is running on {self.api_url}',
                'provider': self.provider,
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e),
                'provider': self.provider,
            }
    
    def analyze_function(self, code: str, signature: str, dependency_summaries: list = None, 
                        temperature: float = None, top_p: float = None, max_tokens: int = None,
                        extra_criteria: str = None, extra_question: str = None) -> str:
        """Get AI summary for a function
        
        Args:
            code: Source code of the function
            signature: Function signature
            dependency_summaries: List of dicts with 'name' and 'summary' for called functions
            temperature: Model temperature (optional, uses default if not provided)
            top_p: Top-p sampling parameter (optional)
            max_tokens: Maximum tokens in response (optional)
        
        Returns:
            str: AI-generated summary in Turkish
        """
        
        # Use provided parameters or fall back to instance defaults
        temp = temperature if temperature is not None else self.temperature
        tp = top_p if top_p is not None else self.top_p
        mt = max_tokens if max_tokens is not None else self.max_tokens
        
        # Build context from dependency summaries
        dependency_context = ""
        if dependency_summaries:
            dependency_context = "\n\nBu fonksiyonun çağırdığı alt fonksiyonlar ve görevleri:\n"
            for dep in dependency_summaries:
                dependency_context += f"\n- {dep['name']}: {dep['summary']}\n"
        
        extra_instructions = ""
        if extra_criteria:
            extra_instructions += f"\nEk kriter: {extra_criteria}\n"
        if extra_question:
            extra_instructions += f"\nEk soru: {extra_question}\n"

        prompt = f"""Bu fonksiyonu analiz et ve SADECE TÜRKÇE yanıt ver.
    Kısa, net ve tekrar etmeyen bir özet üret.

Function Signature: {signature}

Code:
```
{code}
```{dependency_context}
{extra_instructions}

Kelime sınırı olmaksızın şunları açıkla:
1. What the function does
2. Input parameters and their purpose
3. Return value/output
4. Any side effects or important notes

Eğer "Ek soru" verildiyse, özetin sonunda "Ek Soru Yanıtı:" başlığı ile uzun ve detaylı cevap ver.

Summary:"""
        
        started_at = time.perf_counter()

        try:
            response = self._post_chat_with_model_fallback(prompt, temp, tp, mt)
            duration_seconds = round(time.perf_counter() - started_at, 3)
            
            if response.status_code == 200:
                data = response.json()
                usage = data.get('usage', {}) if isinstance(data, dict) else {}
                self.last_call_stats = {
                    'duration_seconds': duration_seconds,
                    'prompt_tokens': int(usage.get('prompt_tokens', 0) or 0),
                    'completion_tokens': int(usage.get('completion_tokens', 0) or 0),
                    'total_tokens': int(usage.get('total_tokens', 0) or 0),
                }
                import re
                summary = self._extract_message_text(data)
                # <think> bloklarını temizle
                summary = re.sub(r'<think>.*?</think>', '', summary, flags=re.DOTALL).strip()
                return summary
            else:
                self.last_call_stats = {
                    'duration_seconds': duration_seconds,
                    'prompt_tokens': 0,
                    'completion_tokens': 0,
                    'total_tokens': 0,
                }
                retry_after = self.rate_limit_remaining() or None
                return f"Error: {self._http_error_message(response, retry_after)}"
        
        except RateLimitCooldownError as e:
            duration_seconds = round(time.perf_counter() - started_at, 3)
            self.last_call_stats = {
                'duration_seconds': duration_seconds,
                'prompt_tokens': 0,
                'completion_tokens': 0,
                'total_tokens': 0,
            }
            return f"Error: {e}"
        except requests.exceptions.Timeout:
            duration_seconds = round(time.perf_counter() - started_at, 3)
            self.last_call_stats = {
                'duration_seconds': duration_seconds,
                'prompt_tokens': 0,
                'completion_tokens': 0,
                'total_tokens': 0,
            }
            return (
                f"Error: {self.provider_display} request timed out after {self.request_timeout} seconds. "
                "Model yüklü ve hazır olduğundan emin olun."
            )
        except requests.exceptions.ConnectionError:
            duration_seconds = round(time.perf_counter() - started_at, 3)
            self.last_call_stats = {
                'duration_seconds': duration_seconds,
                'prompt_tokens': 0,
                'completion_tokens': 0,
                'total_tokens': 0,
            }
            return f"Error: Cannot connect to {self.provider_display} at {self.api_url}. Make sure it's running."
        except Exception as e:
            duration_seconds = round(time.perf_counter() - started_at, 3)
            self.last_call_stats = {
                'duration_seconds': duration_seconds,
                'prompt_tokens': 0,
                'completion_tokens': 0,
                'total_tokens': 0,
            }
            return f"Error: {str(e)}"
    
    def suggest_improvements(self, code: str) -> str:
        """Get improvement suggestions for code"""
        
        prompt = f"""Review this code and suggest 2-3 key improvements for readability, efficiency, or best practices. Be brief.

Code:
```
{code}
```

Suggestions:"""
        
        try:
            response = self._post_chat_with_model_fallback(
                prompt,
                self.temperature,
                self.top_p,
                500,
            )
            
            if response.status_code == 200:
                data = response.json()
                return self._extract_message_text(data)
            else:
                retry_after = self.rate_limit_remaining() or None
                return f"Error: {self._http_error_message(response, retry_after)}"
        
        except RateLimitCooldownError as e:
            return f"Error: {e}"
        except Exception as e:
            return f"Error: {str(e)}"

    def chat(self, messages: list, system_prompt: str = None, max_tokens: int = None) -> str:
        """Send a multi-turn chat and return the full response (non-streaming).
        
        Args:
            messages: list of {"role": "user"|"assistant", "content": "..."} dicts
            system_prompt: optional system-level instruction
            max_tokens: optional token limit override
        
        Returns:
            str: The assistant's reply
        """
        mt = max_tokens if max_tokens is not None else self.max_tokens

        full_messages = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        else:
            full_messages.append({"role": "system", "content": "Yanıt dili zorunlu olarak Türkçe olmalı."})
        full_messages.extend(messages)
        full_messages = self._normalize_messages(full_messages)

        payload = {
            "model": self.model,
            "messages": full_messages,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_tokens": mt,
            "stream": False,
        }

        try:
            self._ensure_not_rate_limited()
            response = self.session.post(
                f"{self.api_url}/chat/completions",
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=self.request_timeout,
            )
            retry_after = self._register_rate_limit(response)
            if self._is_invalid_model_response(response):
                models = self.list_models()
                if models:
                    self.model = models[0]
                    payload["model"] = self.model
                    response = self.session.post(
                        f"{self.api_url}/chat/completions",
                        headers={"Content-Type": "application/json"},
                        json=payload,
                        timeout=self.request_timeout,
                    )
                    retry_after = self._register_rate_limit(response)
            if response.status_code == 200:
                data = response.json()
                return self._extract_message_text(data)
            else:
                return f"Error: {self._http_error_message(response, retry_after)}"
        except RateLimitCooldownError as e:
            return f"Error: {e}"
        except requests.exceptions.Timeout:
            return f"Error: {self.provider_display} isteği zaman aşımına uğradı."
        except requests.exceptions.ConnectionError:
            return f"Error: {self.provider_display} bağlantısı kurulamadı ({self.api_url})."
        except Exception as e:
            return f"Error: {str(e)}"

    def chat_stream(self, messages: list, system_prompt: str = None, max_tokens: int = None):
        """Send a multi-turn chat with SSE streaming; yields token strings one by one.
        
        Args:
            messages: list of {"role": "user"|"assistant", "content": "..."} dicts
            system_prompt: optional system-level instruction
            max_tokens: optional token limit override
        
        Yields:
            str: incremental token content chunks
        """
        import json as _json

        mt = max_tokens if max_tokens is not None else self.max_tokens

        full_messages = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        else:
            full_messages.append({"role": "system", "content": "Yanıt dili zorunlu olarak Türkçe olmalı."})
        full_messages.extend(messages)
        full_messages = self._normalize_messages(full_messages)

        payload = {
            "model": self.model,
            "messages": full_messages,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_tokens": mt,
            "stream": True,
        }

        # Model auto-detect on first attempt
        try:
            self._ensure_not_rate_limited()
            with self.session.post(
                f"{self.api_url}/chat/completions",
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=self.request_timeout,
                stream=True,
            ) as response:
                if self._is_invalid_model_response(response):
                    models = self.list_models()
                    if models:
                        self.model = models[0]
                        payload["model"] = self.model
                    # Re-open with corrected model via non-streaming fallback
                    yield from self._chat_stream_inner(payload)
                    return
                
                if response.status_code != 200:
                    retry_after = self._register_rate_limit(response)
                    message = self._http_error_message(response, retry_after)
                    if retry_after:
                        raise RateLimitCooldownError(message, retry_after)
                    raise RuntimeError(message)

                yield from self._parse_sse_stream(response)

        except (RateLimitCooldownError, RuntimeError):
            # Çağıran katman (chat SSE) ayrıntılı hatayı kendisi bildirir.
            raise
        except requests.exceptions.Timeout:
            yield f"\n\n⚠️ {self.provider_display} isteği zaman aşımına uğradı. Model yüklü mü kontrol edin."
        except requests.exceptions.ConnectionError:
            yield f"\n\n⚠️ {self.provider_display}'ya bağlanılamadı ({self.api_url}). Sunucu çalışıyor mu?"
        except Exception as e:
            yield f"\n\n⚠️ Hata: {str(e)}"

    def _chat_stream_inner(self, payload):
        """Re-attempt a stream with the updated payload (after model auto-fix)."""
        try:
            self._ensure_not_rate_limited()
            with self.session.post(
                f"{self.api_url}/chat/completions",
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=self.request_timeout,
                stream=True,
            ) as response:
                if response.status_code != 200:
                    retry_after = self._register_rate_limit(response)
                    message = self._http_error_message(response, retry_after)
                    if retry_after:
                        raise RateLimitCooldownError(message, retry_after)
                    raise RuntimeError(message)
                yield from self._parse_sse_stream(response)
        except (RateLimitCooldownError, RuntimeError):
            raise
        except Exception as e:
            yield f"\n\n⚠️ Yeniden deneme hatası: {str(e)}"

    def _parse_sse_stream(self, response):
        """Parse an SSE stream response and yield content tokens."""
        import json as _json
        for line in response.iter_lines():
            if not line:
                continue
            if isinstance(line, bytes):
                line = line.decode("utf-8")
            if not line.startswith("data:"):
                continue
            data_str = line[5:].strip()
            if data_str == "[DONE]":
                return
            try:
                data = _json.loads(data_str)
                delta = data.get("choices", [{}])[0].get("delta", {})
                content = delta.get("content")
                if content:
                    yield content
            except _json.JSONDecodeError:
                continue
