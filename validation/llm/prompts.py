"""
LLM 검증용 프롬프트 템플릿
"""

from typing import List, Dict, Any
import json


VERIFICATION_PROMPT = """당신은 Pro*C 코드 파싱 결과를 검증하는 전문가입니다.

## 원본 소스 코드
```
{source}
```

## 파싱 결과
```json
{result}
```

## 검증 체크리스트
다음 각 항목에 대해 PASS/FAIL/WARNING으로 판정하고 이유를 설명해주세요:

{checklist}

## 응답 형식
각 체크 항목에 대해 다음 JSON 형식으로 응답해주세요:
```json
{{
    "checks": [
        {{
            "check_id": "체크 ID",
            "status": "PASS|FAIL|WARNING",
            "message": "판정 이유",
            "details": {{}}
        }}
    ],
    "feedbacks": [
        {{
            "category": "under_decomposition|over_decomposition|accuracy",
            "severity": "error|warning|info",
            "message": "피드백 내용",
            "suggestion": "개선 제안",
            "affected_items": ["영향받는 항목 ID"]
        }}
    ],
    "summary": "전체 검증 요약"
}}
```
"""


def format_verification_prompt(
    template: str,
    source: str,
    result: Any,
    checklist: List[Dict[str, str]]
) -> str:
    """검증 프롬프트 포맷팅
    
    Args:
        template: 프롬프트 템플릿
        source: 원본 소스 코드
        result: 파싱 결과 (JSON 직렬화 가능)
        checklist: 체크리스트 항목
        
    Returns:
        포맷팅된 프롬프트
    """
    # 결과를 JSON 문자열로 변환
    if isinstance(result, str):
        result_str = result
    else:
        result_str = json.dumps(result, ensure_ascii=False, indent=2)
    
    # 체크리스트 포맷팅
    checklist_str = "\n".join([
        f"- [{item['id']}] {item['question']} (severity: {item.get('severity', 'info')})"
        for item in checklist
    ])
    
    return template.format(
        source=source,
        result=result_str,
        checklist=checklist_str
    )


def load_checklist_prompt(checklist_path: str) -> List[Dict[str, str]]:
    """YAML 체크리스트 파일에서 프롬프트 항목 로드
    
    Args:
        checklist_path: 체크리스트 YAML 파일 경로
        
    Returns:
        체크 항목 리스트
    """
    import yaml
    
    with open(checklist_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    
    return data.get('llm_checks', [])


def parse_llm_response(response: str) -> Dict[str, Any]:
    """LLM 응답에서 JSON 추출 및 파싱
    
    Args:
        response: LLM 응답 텍스트
        
    Returns:
        파싱된 결과 딕셔너리
    """
    import re
    
    # JSON 블록 찾기
    json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    else:
        # 전체 응답을 JSON으로 시도
        json_str = response.strip()
    
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return {
            'checks': [],
            'feedbacks': [],
            'summary': response,
            'parse_error': True
        }
