"""
LLM 프롬프트 관리 모듈

SQL 변환 검증을 위한 기본 프롬프트와 커스텀 프롬프트 로드 기능을 제공합니다.
"""

from pathlib import Path
from typing import Optional
from loguru import logger


DEFAULT_PROMPT = """당신은 Pro*C SQL에서 MyBatis SQL로의 변환을 검증하는 전문가입니다.

다음 두 SQL을 비교하여 변환이 올바르게 되었는지 분석해주세요:

## 원본 (Pro*C SQL)
```sql
{asis}
```

## 변환 결과 (MyBatis SQL)
```sql
{tobe}
```

## 검증 항목
1. EXEC SQL 키워드가 올바르게 제거되었는지
2. 호스트 변수(:var)가 MyBatis 파라미터(#{var})로 올바르게 변환되었는지
3. SELECT INTO 절이 적절하게 처리되었는지
4. SQL 문법이 올바른지
5. 테이블명, 컬럼명 등 식별자가 보존되었는지
6. 의미적으로 동일한 SQL인지

## 응답 형식
다음 형식으로 응답해주세요:

### 변환 결과
[✅ 정상 / ⚠️ 주의 필요 / ❌ 오류 발견]

### 상세 분석
- 변환 품질에 대한 간단한 설명

### 발견된 문제 (있는 경우)
- 문제 1
- 문제 2

### 개선 제안 (있는 경우)
- 제안 1
"""


def load_custom_prompt(path: str) -> Optional[str]:
    """
    파일에서 커스텀 프롬프트를 로드합니다.
    
    Args:
        path: 프롬프트 파일 경로 (텍스트 파일)
        
    Returns:
        프롬프트 문자열 또는 None (실패 시)
    """
    file_path = Path(path)
    
    if not file_path.exists():
        logger.error(f"프롬프트 파일을 찾을 수 없습니다: {path}")
        return None
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            prompt = f.read().strip()
        
        # 필수 플레이스홀더 검증
        if '{asis}' not in prompt or '{tobe}' not in prompt:
            logger.warning("프롬프트에 {asis}와 {tobe} 플레이스홀더가 필요합니다")
            return None
        
        logger.info(f"커스텀 프롬프트 로드됨: {path}")
        return prompt
        
    except Exception as e:
        logger.error(f"프롬프트 파일 로드 실패: {e}")
        return None


def save_custom_prompt(path: str, prompt: str) -> bool:
    """
    커스텀 프롬프트를 파일로 저장합니다.
    
    Args:
        path: 저장할 파일 경로
        prompt: 프롬프트 문자열
        
    Returns:
        성공 여부
    """
    try:
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(prompt)
        
        logger.info(f"프롬프트 저장됨: {path}")
        return True
        
    except Exception as e:
        logger.error(f"프롬프트 저장 실패: {e}")
        return False


def format_prompt(prompt: str, asis: str, tobe: str) -> str:
    """
    프롬프트에 SQL을 삽입합니다.
    
    Args:
        prompt: 프롬프트 템플릿
        asis: 원본 SQL
        tobe: 변환된 SQL
        
    Returns:
        포맷된 프롬프트
    """
    return prompt.format(asis=asis, tobe=tobe)
