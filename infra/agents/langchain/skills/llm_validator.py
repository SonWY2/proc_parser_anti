"""
LLM Validator Skill

LLM을 활용한 검증 기능을 제공하는 Skill입니다.
Parser Critic과 SQL Critic 검증을 모두 지원합니다.
"""

from typing import Any, Dict, List, Optional
import logging

from .skill_interface import BaseSkill, SkillResult

logger = logging.getLogger(__name__)


class LLMValidatorSkill(BaseSkill):
    """
    LLM 기반 검증 Skill
    
    청크별 파싱 결과 검증과 MyBatis 변환 결과 검증을 LLM으로 수행합니다.
    
    Input:
        {
            "mode": "parser" | "sql",         # 검증 모드
            "chunks": [...] (parser mode),    # 검증할 코드 청크들
            "mybatis_xmls": [...] (sql mode), # 검증할 MyBatis 변환
            "batch_size": 20 (optional)       # 배치 크기
        }
        
    Output:
        {
            "passed": bool,
            "issues": [...],
            "summary": str
        }
    """
    
    def __init__(self, debug: bool = False, debug_file: str = None):
        self._llm_client = None
        self._prompt_loader = None
        self.debug = debug  # True면 LLM 입/출력 상세 로그
        self.debug_file = debug_file  # 디버그 로그 파일 경로
    
    def _write_debug(self, content: str):
        """디버그 내용을 파일에 기록"""
        if not self.debug:
            return
        
        if self.debug_file:
            with open(self.debug_file, "a", encoding="utf-8") as f:
                f.write(content + "\n")
        else:
            print(content)
    
    @property
    def name(self) -> str:
        return "llm_validator"
    
    @property
    def description(self) -> str:
        return "LLM을 활용한 파싱/SQL 변환 결과 검증"
    
    def _get_llm_client(self):
        """LLM 클라이언트 지연 초기화"""
        if self._llm_client is None:
            from ..llm_client import get_llm_client
            self._llm_client = get_llm_client()
        return self._llm_client
    
    def _get_prompt_loader(self):
        """프롬프트 로더 지연 초기화"""
        if self._prompt_loader is None:
            from ..subagents.subagent_loader import get_subagent_loader
            self._prompt_loader = get_subagent_loader()
        return self._prompt_loader
    
    def validate_input(self, input_data: Any) -> Optional[str]:
        if not isinstance(input_data, dict):
            return "입력은 딕셔너리여야 합니다"
        
        mode = input_data.get("mode", "parser")
        if mode == "parser" and "chunks" not in input_data:
            return "parser 모드에서는 chunks 필드가 필요합니다"
        if mode == "sql" and "mybatis_xmls" not in input_data:
            return "sql 모드에서는 mybatis_xmls 필드가 필요합니다"
        
        return None
    
    def invoke(self, input_data: Any) -> SkillResult:
        """
        LLM 검증 실행
        
        Args:
            input_data: {mode, chunks | mybatis_xmls, batch_size?}
            
        Returns:
            SkillResult with validation results
        """
        error = self.validate_input(input_data)
        if error:
            return SkillResult(success=False, errors=[error])
        
        mode = input_data.get("mode", "parser")
        batch_size = input_data.get("batch_size", 20)
        
        # debug 옵션 반영
        if input_data.get("debug"):
            self.debug = True
        if input_data.get("debug_file"):
            self.debug_file = input_data.get("debug_file")
        
        try:
            if mode == "parser":
                result = self._validate_parser_chunks(
                    input_data["chunks"], 
                    batch_size
                )
            else:  # sql mode
                result = self._validate_sql_conversion(
                    input_data["mybatis_xmls"],
                    batch_size
                )
            
            return SkillResult(success=True, data=result)
            
        except Exception as e:
            logger.exception(f"LLM 검증 실패: {e}")
            return SkillResult(success=False, errors=[str(e)])
    
    def _validate_parser_chunks(
        self, 
        chunks: List[Dict], 
        batch_size: int
    ) -> Dict:
        """Parser Critic: 청크별 파싱 결과 검증"""
        import json
        from ..utils.chunking import chunk_list
        
        llm = self._get_llm_client()
        loader = self._get_prompt_loader()
        
        all_missing = []
        all_wrong = []
        all_reclassifications = []
        
        for chunk in chunks:
            elements = chunk.get("elements", [])
            if not elements:
                continue
            
            code = chunk.get("code", "")
            scope = chunk.get("scope", "unknown")
            
            # 요소가 많으면 배치 단위로 처리
            for batch_idx, element_batch in enumerate(chunk_list(elements, batch_size)):
                logger.info(f"검증: {scope} 배치 {batch_idx + 1} ({len(element_batch)}개)")
                
                # 오분석 검증 프롬프트
                wrong_prompt = loader.get_prompt_section(
                    "parser_critic_agent", 
                    "오분석 검증",
                    fallback=self._get_fallback_wrong_prompt()
                )
                
                try:
                    user_prompt = json.dumps({
                        "code": code,
                        "elements": element_batch
                    }, ensure_ascii=False, indent=2)
                    
                    # 디버그 모드: 입력 출력
                    if self.debug:
                        self._write_debug(f"\n{'='*60}")
                        self._write_debug(f"📤 [Parser Critic] LLM 입력 - {scope}")
                        self._write_debug(f"{'='*60}")
                        self._write_debug(f"[System Prompt]\n{wrong_prompt}")
                        self._write_debug(f"\n[User Prompt]\n{user_prompt}")
                        self._write_debug(f"{'='*60}")
                    
                    result = llm.invoke_with_system(
                        system_prompt=wrong_prompt,
                        user_prompt=user_prompt,
                        parse_json=True
                    )
                    
                    # 디버그 모드: 출력 출력
                    if self.debug:
                        self._write_debug(f"\n📥 [Parser Critic] LLM 출력")
                        self._write_debug(f"{json.dumps(result, ensure_ascii=False, indent=2)}")
                        self._write_debug(f"{'='*60}\n")
                    
                    if isinstance(result, dict):
                        all_wrong.extend(result.get("issues", []))
                        all_reclassifications.extend(
                            result.get("reclassifications", [])
                        )
                        
                except Exception as e:
                    # 디버그 모드: 에러 출력
                    if self.debug:
                        self._write_debug(f"\n❌ [Parser Critic] LLM 호출 실패")
                        self._write_debug(f"Error: {e}")
                        self._write_debug(f"{'='*60}\n")
                    
                    logger.warning(f"LLM 검증 실패 ({scope}): {e}, 룰 기반 폴백")
                    # 룰 기반 폴백
                    fallback = self._rule_based_validation(chunk)
                    all_missing.extend(fallback.get("missing_issues", []))
        
        return {
            "passed": len(all_wrong) == 0 and len(all_missing) == 0,
            "missing_count": len(all_missing),
            "wrong_count": len(all_wrong),
            "reclassification_count": len(all_reclassifications),
            "missing_issues": all_missing,
            "wrong_issues": all_wrong,
            "reclassifications": all_reclassifications
        }
    
    def _validate_sql_conversion(
        self, 
        mybatis_xmls: List[Dict],
        batch_size: int
    ) -> Dict:
        """SQL Critic: MyBatis 변환 결과 검증"""
        import json
        from ..utils.chunking import chunk_list
        
        llm = self._get_llm_client()
        loader = self._get_prompt_loader()
        
        # 검토 대상 필터링
        candidates = [
            {
                "sql_id": m.get("sql_id"),
                "sql_type": m.get("sql_type"),
                "original": m.get("original", ""),
                "converted": m.get("converted", "")
            }
            for m in mybatis_xmls
            if m.get("success") and m.get("converted")
            and m.get("note") != "skip_declare_section"
            and not str(m.get("note", "")).startswith("merged_into_cursor_")
        ]
        
        if not candidates:
            return {
                "passed": True, 
                "issues": [], 
                "summary": "검토 대상 SQL 없음"
            }
        
        # 시스템 프롬프트 로드
        system_prompt = loader.get_prompt(
            "sql_critic_agent"
        )
        
        all_issues = []
        
        for batch_idx, batch in enumerate(chunk_list(candidates, batch_size)):
            logger.info(f"SQL Critic: 배치 {batch_idx + 1} ({len(batch)}개)")
            
            try:
                user_prompt = json.dumps(batch, ensure_ascii=False, indent=2)
                
                # 디버그 모드: 입력 출력
                if self.debug:
                    self._write_debug(f"\n{'='*60}")
                    self._write_debug(f"📤 [SQL Critic] LLM 입력 - 배치 {batch_idx + 1}")
                    self._write_debug(f"{'='*60}")
                    self._write_debug(f"[System Prompt]\n{system_prompt}")
                    self._write_debug(f"\n[User Prompt]\n{user_prompt}")
                    self._write_debug(f"{'='*60}")
                
                result = llm.invoke_with_system(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    parse_json=True
                )
                
                # 디버그 모드: 출력 출력
                if self.debug:
                    self._write_debug(f"\n📥 [SQL Critic] LLM 출력")
                    self._write_debug(f"{json.dumps(result, ensure_ascii=False, indent=2)}")
                    self._write_debug(f"{'='*60}\n")
                
                if isinstance(result, dict):
                    all_issues.extend(result.get("issues", []))
                    
            except Exception as e:
                # 디버그 모드: 에러 출력
                if self.debug:
                    self._write_debug(f"\n❌ [SQL Critic] LLM 호출 실패 - 배치 {batch_idx + 1}")
                    self._write_debug(f"Error: {e}")
                    self._write_debug(f"{'='*60}\n")
                
                logger.warning(f"SQL Critic 배치 {batch_idx + 1} 실패: {e}")
        
        return {
            "passed": len(all_issues) == 0,
            "issues": all_issues,
            "summary": f"총 {len(candidates)}개 SQL 검토, {len(all_issues)}개 이슈"
        }
    
    def _rule_based_validation(self, chunk: Dict) -> Dict:
        """룰 기반 폴백 검증"""
        import re
        
        result = {
            "chunk_id": chunk.get("scope", "unknown"),
            "missing_issues": [],
            "wrong_issues": [],
            "reclassifications": []
        }
        
        code = chunk.get("code", "")
        elements = chunk.get("elements", [])
        
        # 간단한 미분석 체크: EXEC SQL이 추출되지 않은 경우
        exec_sql_count = len(re.findall(r'EXEC\s+SQL', code, re.IGNORECASE))
        sql_elements = [e for e in elements if e.get("category") == "sql_blocks"]
        
        if exec_sql_count > len(sql_elements):
            result["missing_issues"].append({
                "type": "SQL",
                "content": f"EXEC SQL {exec_sql_count}개 중 {len(sql_elements)}개만 추출됨",
                "line": 0
            })
        
        return result
    
    def _get_fallback_wrong_prompt(self) -> str:
        """오분석 검증 폴백 프롬프트"""
        return """당신은 Pro*C 코드 파서의 결과를 검증하는 전문가입니다.

사용자가 원본 코드와 파서가 추출한 결과를 JSON으로 제공합니다.
추출 결과가 정확한지 검증하세요.

## 검증 항목
1. SQL 타입 분류 (SELECT/INSERT/UPDATE/DELETE)
2. 호스트 변수 입력/출력 구분
3. 함수 시그니처 (반환 타입, 파라미터)
4. 변수 타입 정확성

## 입력 JSON 형식
{
  "code": "원본 코드",
  "elements": [추출된 요소 배열]
}

## 출력 형식 (JSON만 출력)
{
  "has_errors": true 또는 false,
  "issues": [
    {
      "element_id": "요소 ID",
      "element_type": "현재 분류된 타입",
      "issue": "문제 설명",
      "correct_value": "수정된 값 (있다면)",
      "severity": "error" | "warning"
    }
  ],
  "reclassifications": [
    {
      "element_id": "요소 ID",
      "from_type": "잘못된 타입",
      "to_type": "올바른 타입"
    }
  ],
  "summary": "요약"
}"""
