"""
LLM 검증용 프롬프트 템플릿 및 유틸리티
"""

import json
from typing import Any, Dict, List, Optional


# 공통 검증 프롬프트 템플릿
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
    source: str,
    result: Any,
    checklist: List[Dict[str, str]]
) -> str:
    """검증 프롬프트 포맷팅
    
    Args:
        source: 원본 소스 코드
        result: 파싱 결과 (JSON 직렬화 가능)
        checklist: 체크리스트 항목들
        
    Returns:
        포맷팅된 프롬프트 문자열
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
    
    return VERIFICATION_PROMPT.format(
        source=source,
        result=result_str,
        checklist=checklist_str
    )


def load_checklist(checklist_name: str) -> List[Dict[str, str]]:
    """체크리스트 파일에서 항목 로드
    
    Args:
        checklist_name: 체크리스트 이름 (예: 'header_parsing')
        
    Returns:
        체크 항목 리스트
    """
    import yaml
    import os
    
    # 현재 파일 위치 기준 checklists 폴더 경로
    current_dir = os.path.dirname(os.path.abspath(__file__))
    checklist_path = os.path.join(current_dir, 'checklists', f'{checklist_name}.yaml')
    
    if not os.path.exists(checklist_path):
        # .yaml 없이 시도
        checklist_path = os.path.join(current_dir, 'checklists', f'{checklist_name}')
        if not os.path.exists(checklist_path):
            return []
            
    with open(checklist_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    
    return data.get('llm_checks', [])
