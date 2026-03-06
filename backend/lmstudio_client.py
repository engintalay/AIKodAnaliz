import requests
import json
from config.config import (
    LMSTUDIO_API_URL,
    LMSTUDIO_DEFAULT_MODEL,
    LMSTUDIO_MAX_TOKENS,
    LMSTUDIO_TEMPERATURE,
    LMSTUDIO_TOP_P,
    CONTEXT_LIMIT_TOKENS,
)
from backend.database import db

class LMStudioClient:
    """Client for LMStudio local AI"""
    
    def __init__(self, user_id=None):
        self.api_url = LMSTUDIO_API_URL
        self.model = LMSTUDIO_DEFAULT_MODEL
        self.max_tokens = LMSTUDIO_MAX_TOKENS
        self.temperature = LMSTUDIO_TEMPERATURE
        self.top_p = LMSTUDIO_TOP_P
        self.context_limit = CONTEXT_LIMIT_TOKENS
        # Local models can have long first-token delays while loading.
        # Increased timeout for local inference (5 minutes)
        self.request_timeout = 300
        self.retry_count = 3

        # Load runtime overrides from ai_settings table (if present)
        self._load_runtime_settings(user_id)

        # Never inherit OS/env proxy settings.
        self.session = requests.Session()
        self.session.trust_env = False

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

            # Per-user override for AI server URL
            if user_id is not None:
                user_rows = db.execute_query(
                    'SELECT ai_api_url FROM user_settings WHERE user_id = ?',
                    [user_id]
                )
                if user_rows:
                    user_row = dict(user_rows[0])
                    user_api_url = (user_row.get('ai_api_url') or '').strip()
                    if user_api_url:
                        self.api_url = user_api_url.rstrip('/')

                    user_model_name = (user_row.get('ai_model_name') or '').strip()
                    if user_model_name:
                        self.model = user_model_name
        except Exception:
            # Keep config defaults if DB is unavailable or malformed.
            pass

    def _is_invalid_model_response(self, response) -> bool:
        """Detect remote LMStudio invalid model errors from HTTP response."""
        if response.status_code != 400:
            return False
        try:
            payload = response.json()
            text = json.dumps(payload, ensure_ascii=False).lower()
        except Exception:
            text = (response.text or '').lower()
        return ('invalid model' in text) or ('invalid model identifier' in text)

    def _build_chat_payload(self, prompt, temperature, top_p, max_tokens):
        return {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "Yanıt dili zorunlu olarak Türkçe olmalı. İngilizce veya başka dil kullanma."
                },
                {"role": "user", "content": prompt}
            ],
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
            "stream": False
        }

    def _post_chat_with_model_fallback(self, prompt, temperature, top_p, max_tokens):
        """Send chat request; if model is invalid, auto-pick first available model and retry once."""
        response = self.session.post(
            f"{self.api_url}/chat/completions",
            headers={"Content-Type": "application/json"},
            json=self._build_chat_payload(prompt, temperature, top_p, max_tokens),
            timeout=self.request_timeout
        )

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
            except Exception:
                # Keep original response if model list/retry fails.
                pass

        return response

    def list_models(self) -> list:
        """Return model IDs from LMStudio /models endpoint."""
        response = self.session.get(f"{self.api_url}/models", timeout=10)
        response.raise_for_status()
        payload = response.json()
        models = payload.get('data', []) if isinstance(payload, dict) else []
        model_ids = []
        for model in models:
            model_id = model.get('id') if isinstance(model, dict) else None
            if model_id:
                model_ids.append(model_id)
        return model_ids
    
    def test_connection(self) -> dict:
        """Test connection to LMStudio"""
        try:
            response = self.session.get(f"{self.api_url}/models", timeout=5)
            if response.status_code == 200:
                return {
                    'status': 'connected',
                    'message': 'Successfully connected to LMStudio'
                }
            else:
                return {
                    'status': 'error',
                    'message': f'LMStudio returned status {response.status_code}'
                }
        except requests.exceptions.ConnectionError:
            return {
                'status': 'error',
                'message': f'Cannot connect to LMStudio. Make sure it is running on {self.api_url}'
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def analyze_function(self, code: str, signature: str, dependency_summaries: list = None, 
                        temperature: float = None, top_p: float = None, max_tokens: int = None) -> str:
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
        
        prompt = f"""Bu fonksiyonu analiz et ve SADECE TÜRKÇE yanıt ver.
    Kısa, net ve tekrar etmeyen bir özet üret.

Function Signature: {signature}

Code:
```
{code}
```{dependency_context}

En fazla 200 kelimeyle şunları açıkla:
1. What the function does
2. Input parameters and their purpose
3. Return value/output
4. Any side effects or important notes

Summary:"""
        
        try:
            response = self._post_chat_with_model_fallback(prompt, temp, tp, mt)
            
            if response.status_code == 200:
                data = response.json()
                summary = data['choices'][0]['message']['content'].strip()
                
                # Return full summary without truncation
                return summary
            else:
                try:
                    detail = response.json()
                except Exception:
                    detail = response.text
                return f"Error: LMStudio returned {response.status_code} - {detail}"
        
        except requests.exceptions.Timeout:
            return (
                f"Error: LMStudio request timed out after {self.request_timeout} seconds. "
                "Model yüklü ve hazır olduğundan emin olun."
            )
        except requests.exceptions.ConnectionError:
            return f"Error: Cannot connect to LMStudio at {self.api_url}. Make sure it's running."
        except Exception as e:
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
                return data['choices'][0]['message']['content'].strip()
            else:
                return f"Error: {response.status_code}"
        
        except Exception as e:
            return f"Error: {str(e)}"
