"""
LangChain 기반 LLM 클라이언트

ChatOpenAI를 래핑하여 프로젝트 전반에서 일관된 LLM 호출을 제공합니다.
환경변수 기반 설정을 사용하며, JSON 응답 파싱과 배치 처리를 지원합니다.
"""

import json
import re
import logging
from typing import Any, Dict, List, Optional, Union

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate

from .config import LLMConfig

load_dotenv()
logger = logging.getLogger(__name__)


class LLMClient:
    """
    통합 LLM 클라이언트
    
    환경변수 기반 설정으로 ChatOpenAI를 초기화하고,
    JSON 응답 파싱 및 배치 처리를 지원합니다.
    
    Example:
        client = LLMClient()
        result = client.invoke("분석해주세요", {"data": "..."})
        
        # 시스템 프롬프트와 함께 사용
        result = client.invoke_with_system(
            system_prompt="당신은 SQL 전문가입니다.",
            user_prompt="{sql}을 검증해주세요",
            variables={"sql": "SELECT * FROM users"}
        )
    """
    
    def __init__(self, config: Optional[LLMConfig] = None):
        """
        Args:
            config: LLM 설정. None이면 환경변수에서 로드
        """
        self.config = config or LLMConfig.from_env()
        self._llm: Optional[ChatOpenAI] = None
        self._json_parser = JsonOutputParser()
    
    @property
    def llm(self) -> ChatOpenAI:
        """ChatOpenAI 인스턴스 (지연 초기화)"""
        if self._llm is None:
            self._llm = ChatOpenAI(**self.config.to_dict())
            logger.info(f"LLM 초기화: model={self.config.model}, base_url={self.config.base_url}")
        return self._llm
    
    def invoke(
        self, 
        prompt: str, 
        variables: Optional[Dict[str, Any]] = None,
        parse_json: bool = True
    ) -> Union[Dict, str]:
        """
        단순 프롬프트 호출
        
        Args:
            prompt: 프롬프트 템플릿 (변수는 {var} 형식)
            variables: 프롬프트 변수
            parse_json: True면 JSON 파싱 시도
            
        Returns:
            파싱된 JSON 또는 원본 문자열
        """
        if variables:
            for key, value in variables.items():
                if isinstance(value, (dict, list)):
                    value = json.dumps(value, ensure_ascii=False, indent=2)
                prompt = prompt.replace(f"{{{key}}}", str(value))
        
        response = self.llm.invoke([HumanMessage(content=prompt)])
        content = response.content
        
        if parse_json:
            return self._parse_json_response(content)
        return content
    
    def invoke_with_system(
        self,
        system_prompt: str,
        user_prompt: str,
        variables: Optional[Dict[str, Any]] = None,
        parse_json: bool = True
    ) -> Union[Dict, str]:
        """
        시스템 프롬프트와 함께 호출
        
        Args:
            system_prompt: 시스템 프롬프트
            user_prompt: 사용자 프롬프트
            variables: 프롬프트 변수 (system_prompt와 user_prompt 모두에 적용)
            parse_json: True면 JSON 파싱 시도
            
        Returns:
            파싱된 JSON 또는 원본 문자열
        """
        if variables:
            for key, value in variables.items():
                if isinstance(value, (dict, list)):
                    value = json.dumps(value, ensure_ascii=False, indent=2)
                str_value = str(value)
                system_prompt = system_prompt.replace(f"{{{key}}}", str_value)
                user_prompt = user_prompt.replace(f"{{{key}}}", str_value)
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        response = self.llm.invoke(messages)
        content = response.content
        
        logger.debug(f"LLM 응답: {len(content)} chars")
        
        if parse_json:
            return self._parse_json_response(content)
        return content
    
    def invoke_batch(
        self,
        items: List[Any],
        prompt_template: str,
        item_key: str = "item",
        system_prompt: Optional[str] = None,
        batch_size: int = 10,
        parse_json: bool = True
    ) -> List[Union[Dict, str]]:
        """
        배치 처리
        
        Args:
            items: 처리할 항목 리스트
            prompt_template: 프롬프트 템플릿 ({item_key} 변수 포함)
            item_key: 항목을 참조하는 변수명
            system_prompt: 시스템 프롬프트 (선택)
            batch_size: 배치 크기
            parse_json: True면 JSON 파싱 시도
            
        Returns:
            결과 리스트
        """
        from .utils.chunking import chunk_list
        
        results = []
        
        for batch_idx, batch in enumerate(chunk_list(items, batch_size)):
            logger.info(f"배치 {batch_idx + 1} 처리 ({len(batch)}개 항목)")
            
            variables = {item_key: batch}
            
            if system_prompt:
                result = self.invoke_with_system(
                    system_prompt=system_prompt,
                    user_prompt=prompt_template,
                    variables=variables,
                    parse_json=parse_json
                )
            else:
                result = self.invoke(
                    prompt=prompt_template,
                    variables=variables,
                    parse_json=parse_json
                )
            
            if isinstance(result, list):
                results.extend(result)
            else:
                results.append(result)
        
        return results
    
    def _parse_json_response(self, content: str) -> Union[Dict, str]:
        """
        LLM 응답에서 JSON 추출 및 파싱
        
        ```json ... ``` 블록이 있으면 해당 내용만 추출
        """
        try:
            # JSON 코드 블록 추출 시도
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```', content)
            if json_match:
                content = json_match.group(1)
            
            # 또는 첫 번째 { 부터 마지막 } 까지
            elif '{' in content and '}' in content:
                start = content.find('{')
                end = content.rfind('}') + 1
                content = content[start:end]
            
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON 파싱 실패: {e}")
            logger.debug(f"원본 내용: {content[:200]}...")
            return {"raw": content, "parse_error": str(e)}


# 싱글톤 인스턴스 (편의용)
_default_client: Optional[LLMClient] = None


def get_llm_client(config: Optional[LLMConfig] = None) -> LLMClient:
    """기본 LLM 클라이언트 인스턴스 반환"""
    global _default_client
    if _default_client is None or config is not None:
        _default_client = LLMClient(config)
    return _default_client
