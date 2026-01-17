"""
LLM 클라이언트

서브에이전트가 사용하는 LLM API 클라이언트입니다.
OpenAI 호환 API (vLLM, OpenAI, 등)를 지원합니다.
"""

import os
import json
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
import requests


@dataclass
class LLMConfig:
    """LLM 설정"""
    endpoint: str
    api_key: Optional[str] = None
    model: Optional[str] = None
    timeout: int = 60
    
    @classmethod
    def from_env(cls) -> 'LLMConfig':
        """환경 변수에서 설정 로드"""
        return cls(
            endpoint=os.getenv('LLM_API_ENDPOINT', os.getenv('VLLM_API_ENDPOINT', '')).rstrip('/'),
            api_key=os.getenv('LLM_API_KEY', os.getenv('OPENAI_API_KEY', '')),
            model=os.getenv('LLM_MODEL', None),
            timeout=int(os.getenv('LLM_TIMEOUT', '60'))
        )


class LLMClient:
    """OpenAI 호환 LLM API 클라이언트"""
    
    def __init__(self, config: Optional[LLMConfig] = None):
        """
        Args:
            config: LLM 설정 (None이면 환경 변수에서 로드)
        """
        self.config = config or LLMConfig.from_env()
        self._model_name: Optional[str] = self.config.model
    
    @property
    def is_configured(self) -> bool:
        """API가 설정되었는지 확인"""
        return bool(self.config.endpoint)
    
    def get_model_name(self) -> Optional[str]:
        """모델 이름 조회 (자동 탐색)"""
        if self._model_name:
            return self._model_name
        
        if not self.is_configured:
            return None
        
        try:
            headers = {}
            if self.config.api_key:
                headers['Authorization'] = f'Bearer {self.config.api_key}'
            
            response = requests.get(
                f"{self.config.endpoint}/models",
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            models = data.get('data', [])
            
            if models:
                self._model_name = models[0].get('id')
                return self._model_name
        except Exception:
            pass
        
        return None
    
    def chat(
        self, 
        messages: List[Dict[str, str]], 
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096
    ) -> Dict[str, Any]:
        """
        Chat completion API 호출
        
        Args:
            messages: 대화 메시지 목록 [{"role": "user", "content": "..."}]
            tools: 사용 가능한 도구 스키마 목록
            temperature: 생성 온도
            max_tokens: 최대 토큰 수
            
        Returns:
            {
                'success': bool,
                'content': str,  # 응답 텍스트
                'tool_calls': List[Dict],  # 도구 호출 목록
                'error': str,
                'usage': Dict  # 토큰 사용량
            }
        """
        if not self.is_configured:
            return {
                'success': False,
                'content': '',
                'tool_calls': [],
                'error': 'API 엔드포인트가 설정되지 않았습니다',
                'usage': {}
            }
        
        model_name = self.get_model_name()
        if not model_name:
            return {
                'success': False,
                'content': '',
                'tool_calls': [],
                'error': '모델을 찾을 수 없습니다',
                'usage': {}
            }
        
        try:
            headers = {'Content-Type': 'application/json'}
            if self.config.api_key:
                headers['Authorization'] = f'Bearer {self.config.api_key}'
            
            payload = {
                'model': model_name,
                'messages': messages,
                'temperature': temperature,
                'max_tokens': max_tokens
            }
            
            # 도구가 있으면 추가
            if tools:
                payload['tools'] = [
                    {'type': 'function', 'function': tool}
                    for tool in tools
                ]
                payload['tool_choice'] = 'auto'
            
            response = requests.post(
                f"{self.config.endpoint}/chat/completions",
                headers=headers,
                json=payload,
                timeout=self.config.timeout
            )
            response.raise_for_status()
            
            result = response.json()
            choice = result['choices'][0]
            message = choice['message']
            
            # 도구 호출 파싱
            tool_calls = []
            if 'tool_calls' in message:
                for tc in message['tool_calls']:
                    tool_calls.append({
                        'id': tc.get('id', ''),
                        'name': tc['function']['name'],
                        'arguments': json.loads(tc['function']['arguments'])
                    })
            
            return {
                'success': True,
                'content': message.get('content', ''),
                'tool_calls': tool_calls,
                'error': '',
                'usage': result.get('usage', {})
            }
            
        except requests.Timeout:
            return {
                'success': False,
                'content': '',
                'tool_calls': [],
                'error': f'요청 시간 초과 ({self.config.timeout}초)',
                'usage': {}
            }
        except requests.RequestException as e:
            return {
                'success': False,
                'content': '',
                'tool_calls': [],
                'error': f'API 요청 실패: {str(e)}',
                'usage': {}
            }
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            return {
                'success': False,
                'content': '',
                'tool_calls': [],
                'error': f'응답 파싱 실패: {str(e)}',
                'usage': {}
            }
