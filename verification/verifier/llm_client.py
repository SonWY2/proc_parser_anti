"""
LLM API 클라이언트

verifier 모듈에서 LLM 기반 검증을 위해 사용하는 클라이언트입니다.
"""

import os
import json
from typing import Any, Dict, List, Optional
import requests
from dataclasses import dataclass


@dataclass
class LLMResponse:
    """LLM 응답 결과"""
    success: bool
    content: str
    error: str = ""
    model: str = ""


class LLMClient:
    """LLM API 클라이언트 (OpenAI 및 호환 API 지원)"""
    
    O1_MODELS = ['o1-mini', 'o1-preview', 'o1']
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        endpoint: Optional[str] = None,
    ):
        """
        Args:
            api_key: OpenAI API 키 (None이면 환경변수에서 로드)
            model: 모델 이름 (None이면 환경변수에서 로드)
            endpoint: API 엔드포인트 (None이면 OpenAI 기본값)
        """
        self.api_key = api_key or os.getenv('OPENAI_API_KEY', '')
        self.model_name = model or os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
        self.endpoint = (endpoint or os.getenv('OPENAI_API_ENDPOINT', 'https://api.openai.com/v1')).rstrip('/')
    
    @property
    def is_configured(self) -> bool:
        """API가 설정되었는지 확인"""
        return bool(self.api_key)
    
    def _is_o1_model(self) -> bool:
        """o1 시리즈 모델인지 확인"""
        return any(self.model_name.startswith(m) for m in self.O1_MODELS)
    
    def _get_headers(self) -> Dict[str, str]:
        """API 요청 헤더"""
        return {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}'
        }
    
    def chat(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """
        LLM에 프롬프트를 전송하고 응답을 받습니다.
        
        Args:
            prompt: 사용자 프롬프트
            system_prompt: 시스템 프롬프트 (선택)
            temperature: 생성 온도 (o1 모델은 무시)
            max_tokens: 최대 토큰 수
            
        Returns:
            LLMResponse: 응답 결과
        """
        if not self.is_configured:
            return LLMResponse(
                success=False,
                content="",
                error="API key not configured. Set OPENAI_API_KEY environment variable.",
            )
        
        messages = []
        if system_prompt and not self._is_o1_model():
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": self.model_name,
            "messages": messages,
        }
        
        if self._is_o1_model():
            payload["max_completion_tokens"] = max_tokens
        else:
            payload["temperature"] = temperature
            payload["max_tokens"] = max_tokens
        
        try:
            response = requests.post(
                f"{self.endpoint}/chat/completions",
                headers=self._get_headers(),
                json=payload,
                timeout=120,
            )
            response.raise_for_status()
            
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            
            return LLMResponse(
                success=True,
                content=content,
                model=self.model_name,
            )
            
        except requests.Timeout:
            return LLMResponse(success=False, content="", error="Request timeout")
        except requests.RequestException as e:
            return LLMResponse(success=False, content="", error=f"Request failed: {e}")
        except (KeyError, IndexError) as e:
            return LLMResponse(success=False, content="", error=f"Response parsing failed: {e}")
    
    def verify_sql_metadata(
        self,
        raw_sql: str,
        metadata: Dict[str, Any],
    ) -> LLMResponse:
        """
        SQL 메타데이터 검증을 위한 LLM 호출
        
        Args:
            raw_sql: 원본 Pro*C SQL 구문
            metadata: 분석된 메타데이터 (input_host_vars, output_host_vars, mybatis_sql 등)
            
        Returns:
            LLMResponse: 검증 결과
        """
        prompt = self._build_sql_metadata_prompt(raw_sql, metadata)
        return self.chat(prompt)
    
    def _build_sql_metadata_prompt(self, raw_sql: str, metadata: Dict[str, Any]) -> str:
        """SQL 메타데이터 검증 프롬프트 생성"""
        metadata_json = json.dumps(metadata, ensure_ascii=False, indent=2)
        
        return f"""당신은 Pro*C SQL 파싱 결과를 검증하는 전문가입니다.

## 원본 Pro*C SQL 구문
```sql
{raw_sql}
```

## 분석된 메타데이터
```json
{metadata_json}
```

## 검증 항목
다음 각 항목을 검증하고 PASS/FAIL로 판정해주세요:

1. **input_host_vars (입력 호스트 변수)**
   - WHERE, SET, VALUES 등 입력으로 사용되는 모든 호스트 변수(:var)가 추출되었는지 확인
   - INTO 절의 변수는 출력이므로 제외해야 함

2. **output_host_vars (출력 호스트 변수)**
   - INTO 절에 있는 모든 출력 호스트 변수가 추출되었는지 확인
   - 인디케이터 변수(:ind_xxx)도 포함되어야 함

3. **alias (컬럼 별칭)**
   - SELECT 절의 AS로 정의된 alias가 올바르게 분석되었는지 확인

4. **mybatis_sql (MyBatis 변환)**
   - 모든 호스트 변수(:var)가 #{{varName}} 형식으로 변환되었는지 확인
   - snake_case가 camelCase로 변환되었는지 확인
   - INTO 절이 제거되었는지 확인

## 응답 형식
반드시 다음 JSON 형식으로만 응답해주세요:
```json
{{
    "input_host_vars": {{
        "status": "PASS|FAIL",
        "expected": ["누락된 변수 또는 올바른 목록"],
        "actual": ["분석된 목록"],
        "message": "판정 이유"
    }},
    "output_host_vars": {{
        "status": "PASS|FAIL",
        "expected": ["누락된 변수 또는 올바른 목록"],
        "actual": ["분석된 목록"],
        "message": "판정 이유"
    }},
    "alias": {{
        "status": "PASS|FAIL",
        "expected": ["올바른 alias 목록"],
        "actual": ["분석된 alias 목록"],
        "message": "판정 이유"
    }},
    "mybatis_sql": {{
        "status": "PASS|FAIL",
        "issues": ["발견된 문제점"],
        "message": "판정 이유"
    }},
    "overall": {{
        "status": "PASS|FAIL",
        "summary": "전체 검증 요약"
    }}
}}
```
"""
