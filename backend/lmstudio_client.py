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
    
    def test_connection(self) -> dict:
        """Test connection to LMStudio"""
        try:
            response = requests.get(f"{self.api_url}/models", timeout=5)
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
    
    def analyze_function(self, code: str, signature: str) -> str:
        """Get AI summary for a function"""
        
        prompt = f"""You are a code analyzer. Analyze this function and provide a brief summary of what it does, its inputs, and outputs. Be concise and avoid repetition.

Function Signature: {signature}

Code:
```
{code}
```

Provide a clear, concise summary (max 200 words) of:
1. What the function does
2. Input parameters and their purpose
3. Return value/output
4. Any side effects or important notes

Summary:"""
        
        try:
            response = requests.post(
                f"{self.api_url}/chat/completions",
                headers={"Content-Type": "application/json"},
                json={
                    "model": "local-model",
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": self.temperature,
                    "top_p": self.top_p,
                    "max_tokens": self.max_tokens,
                    "stream": False
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                summary = data['choices'][0]['message']['content'].strip()
                
                # Limit output to prevent repetition/rambling
                if len(summary) > 500:
                    summary = summary[:500] + "..."
                
                return summary
            else:
                return f"Error: LMStudio returned {response.status_code}"
        
        except requests.exceptions.Timeout:
            return "Error: LMStudio request timed out. Check if model is loaded."
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
            response = requests.post(
                f"{self.api_url}/chat/completions",
                headers={"Content-Type": "application/json"},
                json={
                    "model": "local-model",
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": self.temperature,
                    "max_tokens": 500,
                    "stream": False
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                return data['choices'][0]['message']['content'].strip()
            else:
                return f"Error: {response.status_code}"
        
        except Exception as e:
            return f"Error: {str(e)}"
