"""
vLLM API 클라이언트 모듈

requests를 사용하여 OpenAI 호환 API와 통신합니다.
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any
import requests
from dotenv import load_dotenv
from loguru import logger

from .prompt import DEFAULT_PROMPT, format_prompt


class LLMClient:
    """vLLM API 클라이언트 (OpenAI 호환 스펙)"""
    
    def __init__(self, env_path: Optional[str] = None):
        """
        클라이언트를 초기화합니다.
        
        Args:
            env_path: .env 파일 경로 (None이면 자동 탐색)
        """
        # .env 파일 로드
        if env_path:
            load_dotenv(env_path)
        else:
            # 현재 디렉토리부터 상위로 .env 탐색
            load_dotenv()
        
        self.endpoint = os.getenv('VLLM_API_ENDPOINT', '').rstrip('/')
        self._model_name: Optional[str] = None
        self._available = None
        
        logger.debug(f"LLMClient 초기화: endpoint={self.endpoint}")
    
    @property
    def is_configured(self) -> bool:
        """API 엔드포인트가 설정되었는지"""
        return bool(self.endpoint)
    
    @property
    def is_available(self) -> bool:
        """API가 사용 가능한지 확인"""
        if self._available is not None:
            return self._available
        
        if not self.is_configured:
            self._available = False
            return False
        
        try:
            response = requests.get(
                f"{self.endpoint}/models",
                timeout=5
            )
            self._available = response.status_code == 200
        except requests.RequestException:
            self._available = False
        
        return self._available
    
    def get_model_name(self) -> Optional[str]:
        """
        /v1/models 엔드포인트에서 모델 이름을 가져옵니다.
        
        Returns:
            모델 이름 또는 None
        """
        if self._model_name:
            return self._model_name
        
        if not self.is_configured:
            logger.warning("API 엔드포인트가 설정되지 않았습니다")
            return None
        
        try:
            response = requests.get(
                f"{self.endpoint}/models",
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            models = data.get('data', [])
            
            if models:
                self._model_name = models[0].get('id')
                logger.info(f"모델 로드됨: {self._model_name}")
                return self._model_name
            else:
                logger.warning("사용 가능한 모델이 없습니다")
                return None
                
        except requests.RequestException as e:
            logger.error(f"모델 정보 조회 실패: {e}")
            return None
    
    def analyze_conversion(
        self, 
        asis: str, 
        tobe: str, 
        prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2048
    ) -> Dict[str, Any]:
        """
        LLM을 사용하여 SQL 변환을 분석합니다.
        
        Args:
            asis: 원본 Pro*C SQL
            tobe: 변환된 MyBatis SQL
            prompt: 커스텀 프롬프트 (None이면 기본 프롬프트 사용)
            temperature: 생성 온도 (0.0 ~ 1.0)
            max_tokens: 최대 토큰 수
            
        Returns:
            {
                'success': bool,
                'response': str,  # LLM 응답
                'error': str,     # 에러 메시지 (실패 시)
                'model': str      # 사용된 모델 이름
            }
        """
        if not self.is_configured:
            return {
                'success': False,
                'response': '',
                'error': 'API 엔드포인트가 설정되지 않았습니다. .env 파일에 VLLM_API_ENDPOINT를 설정하세요.',
                'model': None
            }
        
        model_name = self.get_model_name()
        if not model_name:
            return {
                'success': False,
                'response': '',
                'error': '모델을 불러올 수 없습니다. API 서버 상태를 확인하세요.',
                'model': None
            }
        
        # 프롬프트 포맷팅
        template = prompt if prompt else DEFAULT_PROMPT
        formatted_prompt = format_prompt(template, asis, tobe)
        
        # API 요청
        try:
            payload = {
                'model': model_name,
                'messages': [
                    {
                        'role': 'user',
                        'content': formatted_prompt
                    }
                ],
                'temperature': temperature,
                'max_tokens': max_tokens
            }
            
            logger.debug(f"API 요청: model={model_name}, temperature={temperature}")
            
            response = requests.post(
                f"{self.endpoint}/chat/completions",
                json=payload,
                timeout=60
            )
            response.raise_for_status()
            
            result = response.json()
            content = result['choices'][0]['message']['content']
            
            logger.info("LLM 분석 완료")
            
            return {
                'success': True,
                'response': content,
                'error': '',
                'model': model_name
            }
            
        except requests.Timeout:
            error_msg = "API 요청 시간이 초과되었습니다"
            logger.error(error_msg)
            return {
                'success': False,
                'response': '',
                'error': error_msg,
                'model': model_name
            }
        except requests.RequestException as e:
            error_msg = f"API 요청 실패: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'response': '',
                'error': error_msg,
                'model': model_name
            }
        except (KeyError, IndexError) as e:
            error_msg = f"API 응답 파싱 실패: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'response': '',
                'error': error_msg,
                'model': model_name
            }
    
    def test_connection(self) -> Dict[str, Any]:
        """
        API 연결을 테스트합니다.
        
        Returns:
            {
                'connected': bool,
                'endpoint': str,
                'model': str,
                'error': str
            }
        """
        result = {
            'connected': False,
            'endpoint': self.endpoint,
            'model': None,
            'error': ''
        }
        
        if not self.is_configured:
            result['error'] = 'VLLM_API_ENDPOINT가 설정되지 않았습니다'
            return result
        
        model_name = self.get_model_name()
        if model_name:
            result['connected'] = True
            result['model'] = model_name
        else:
            result['error'] = 'API에 연결할 수 없거나 모델이 없습니다'
        
        return result
