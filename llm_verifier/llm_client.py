"""
LLM API 클라이언트 모듈

OpenAI API 및 OpenAI 호환 API(vLLM 등)와 통신합니다.
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any, List
import requests
from dotenv import load_dotenv
from loguru import logger

from .prompts import VERIFICATION_PROMPT, format_verification_prompt


class LLMClient:
    """LLM API 클라이언트 (OpenAI 및 호환 API 지원)"""
    
    # o1 시리즈 모델들 (temperature 미지원)
    O1_MODELS = ['o1-mini', 'o1-preview', 'o1']
    
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
        
        # OpenAI API 설정
        self.api_key = os.getenv('OPENAI_API_KEY', '')
        self.model_name = os.getenv('OPENAI_MODEL', 'o1-mini')
        
        # 엔드포인트 (기본값: OpenAI)
        self.endpoint = os.getenv(
            'VLLM_API_ENDPOINT', 
            'https://api.openai.com/v1'
        ).rstrip('/')
        
        self._available = None
        
        logger.debug(f"LLMClient 초기화: endpoint={self.endpoint}, model={self.model_name}")
    
    @property
    def is_configured(self) -> bool:
        """API가 설정되었는지"""
        return bool(self.api_key) or bool(self.endpoint and 'openai.com' not in self.endpoint)
    
    @property
    def is_available(self) -> bool:
        """API가 사용 가능한지 확인"""
        if self._available is not None:
            return self._available
        
        if not self.is_configured:
            self._available = False
            return False
        
        try:
            headers = self._get_headers()
            response = requests.get(
                f"{self.endpoint}/models",
                headers=headers,
                timeout=5
            )
            self._available = response.status_code == 200
        except requests.RequestException:
            self._available = False
        
        return self._available
    
    def _get_headers(self) -> Dict[str, str]:
        """API 요청 헤더 생성"""
        headers = {
            'Content-Type': 'application/json'
        }
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
        return headers
    
    def _is_o1_model(self) -> bool:
        """o1 시리즈 모델인지 확인"""
        return any(self.model_name.startswith(m) for m in self.O1_MODELS)
    
    def get_model_name(self) -> Optional[str]:
        """
        모델 이름을 반환합니다.
        
        Returns:
            모델 이름
        """
        if self.model_name:
            return self.model_name
        
        # 환경변수에 모델이 없으면 API에서 조회
        if not self.is_configured:
            logger.warning("API가 설정되지 않았습니다")
            return None
        
        try:
            headers = self._get_headers()
            response = requests.get(
                f"{self.endpoint}/models",
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            models = data.get('data', [])
            
            if models:
                self.model_name = models[0].get('id')
                logger.info(f"모델 로드됨: {self.model_name}")
                return self.model_name
            else:
                logger.warning("사용 가능한 모델이 없습니다")
                return None
                
        except requests.RequestException as e:
            logger.error(f"모델 정보 조회 실패: {e}")
            return None
    
    def verify(
        self,
        source: str,
        result: str,
        checklist: List[Dict[str, str]],
        prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096
    ) -> Dict[str, Any]:
        """
        LLM을 사용하여 변환 결과를 검증합니다.
        
        Args:
            source: 원본 소스 코드
            result: 변환 결과 (JSON 문자열)
            checklist: 체크리스트 항목 리스트
            prompt: 커스텀 프롬프트 (None이면 기본 프롬프트)
            temperature: 생성 온도 (o1 모델은 무시)
            max_tokens: 최대 토큰 수
            
        Returns:
            {
                'success': bool,
                'response': str,
                'error': str,
                'model': str
            }
        """
        if not self.is_configured:
            return {
                'success': False,
                'response': '',
                'error': 'API가 설정되지 않았습니다. OPENAI_API_KEY를 설정하세요.',
                'model': None
            }
        
        model_name = self.get_model_name()
        if not model_name:
            return {
                'success': False,
                'response': '',
                'error': '모델을 불러올 수 없습니다.',
                'model': None
            }
        
        # 프롬프트 포맷팅
        template = prompt if prompt else VERIFICATION_PROMPT
        formatted_prompt = format_verification_prompt(
            template, source, result, checklist
        )
        
        # API 요청 페이로드 구성
        payload = {
            'model': model_name,
            'messages': [
                {
                    'role': 'user',
                    'content': formatted_prompt
                }
            ]
        }
        
        # o1 모델은 temperature와 max_tokens 대신 max_completion_tokens 사용
        if self._is_o1_model():
            payload['max_completion_tokens'] = max_tokens
            logger.debug(f"o1 모델 감지: temperature 파라미터 제외")
        else:
            payload['temperature'] = temperature
            payload['max_tokens'] = max_tokens
        
        # API 요청
        try:
            headers = self._get_headers()
            
            logger.debug(f"API 요청: model={model_name}")
            
            response = requests.post(
                f"{self.endpoint}/chat/completions",
                headers=headers,
                json=payload,
                timeout=120  # o1 모델은 시간이 더 걸릴 수 있음
            )
            response.raise_for_status()
            
            result_json = response.json()
            content = result_json['choices'][0]['message']['content']
            
            logger.info("LLM 검증 완료")
            
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
            result['error'] = 'OPENAI_API_KEY가 설정되지 않았습니다'
            return result
        
        try:
            headers = self._get_headers()
            response = requests.get(
                f"{self.endpoint}/models",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                result['connected'] = True
                result['model'] = self.model_name
            else:
                result['error'] = f"API 응답 코드: {response.status_code}"
        except requests.RequestException as e:
            result['error'] = f"연결 실패: {str(e)}"
        
        return result
