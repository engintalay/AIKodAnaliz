import requests
import json
from config.config import LMSTUDIO_API_URL, LMSTUDIO_MAX_TOKENS, LMSTUDIO_TEMPERATURE, LMSTUDIO_TOP_P, CONTEXT_LIMIT_TOKENS

class LMStudioClient:
    """Client for LMStudio local AI"""
    
    def __init__(self):
        self.api_url = LMSTUDIO_API_URL
        self.max_tokens = LMSTUDIO_MAX_TOKENS
        self.temperature = LMSTUDIO_TEMPERATURE
        self.top_p = LMSTUDIO_TOP_P
        self.context_limit = CONTEXT_LIMIT_TOKENS
        # Local models can have long first-token delays while loading.
        # Increased timeout for local inference (5 minutes)
        self.request_timeout = 300
        # Never inherit OS/env proxy settings.
        self.session = requests.Session()
        self.session.trust_env = False
    
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
                'message': 'Cannot connect to LMStudio. Make sure it is running on localhost:1234'
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def analyze_function(self, code: str, signature: str, dependency_summaries: list = None) -> str:
        """Get AI summary for a function
        
        Args:
            code: Source code of the function
            signature: Function signature
            dependency_summaries: List of dicts with 'name' and 'summary' for called functions
        
        Returns:
            str: AI-generated summary in Turkish
        """
        
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
            response = self.session.post(
                f"{self.api_url}/chat/completions",
                headers={"Content-Type": "application/json"},
                json={
                    "model": "local-model",
                    "messages": [
                        {
                            "role": "system",
                            "content": "Yanıt dili zorunlu olarak Türkçe olmalı. İngilizce veya başka dil kullanma."
                        },
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": self.temperature,
                    "top_p": self.top_p,
                    "max_tokens": self.max_tokens,
                    "stream": False
                },
                timeout=self.request_timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                summary = data['choices'][0]['message']['content'].strip()
                
                # Return full summary without truncation
                return summary
            else:
                return f"Error: LMStudio returned {response.status_code}"
        
        except requests.exceptions.Timeout:
            return (
                f"Error: LMStudio request timed out after {self.request_timeout} seconds. "
                "Model yüklü ve hazır olduğundan emin olun."
            )
        except requests.exceptions.ConnectionError:
            return "Error: Cannot connect to LMStudio. Make sure it's running."
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
            response = self.session.post(
                f"{self.api_url}/chat/completions",
                headers={"Content-Type": "application/json"},
                json={
                    "model": "local-model",
                    "messages": [
                        {
                            "role": "system",
                            "content": "Yanıt dili zorunlu olarak Türkçe olmalı. İngilizce veya başka dil kullanma."
                        },
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": self.temperature,
                    "max_tokens": 500,
                    "stream": False
                },
                timeout=self.request_timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                return data['choices'][0]['message']['content'].strip()
            else:
                return f"Error: {response.status_code}"
        
        except Exception as e:
            return f"Error: {str(e)}"
