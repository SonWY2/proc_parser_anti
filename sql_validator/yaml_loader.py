"""
YAML 파일 로더 모듈

sql과 parsed_sql 키를 포함한 YAML 파일을 로드합니다.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
import yaml
from loguru import logger


def load_yaml(path: str) -> List[Dict[str, Any]]:
    """
    YAML 파일을 로드하여 SQL 항목 리스트를 반환합니다.
    
    Args:
        path: YAML 파일 경로
        
    Returns:
        각 항목이 {'sql': str, 'parsed_sql': str} 형태인 리스트
        
    Raises:
        FileNotFoundError: 파일이 존재하지 않을 경우
        yaml.YAMLError: YAML 파싱 오류
        ValueError: 필수 키가 없는 경우
    """
    file_path = Path(path)
    
    if not file_path.exists():
        logger.error(f"파일을 찾을 수 없습니다: {path}")
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {path}")
    
    logger.info(f"YAML 파일 로드: {path}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    
    if data is None:
        logger.warning("빈 YAML 파일입니다")
        return []
    
    # 리스트가 아닌 경우 리스트로 변환
    if isinstance(data, dict):
        data = [data]
    
    if not isinstance(data, list):
        logger.error(f"잘못된 YAML 형식: 리스트 또는 딕셔너리가 필요합니다")
        raise ValueError("잘못된 YAML 형식: 리스트 또는 딕셔너리가 필요합니다")
    
    # 각 항목 검증
    validated_items = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            logger.warning(f"항목 {i}: 딕셔너리가 아닙니다, 건너뜁니다")
            continue
            
        if 'sql' not in item:
            logger.warning(f"항목 {i}: 'sql' 키가 없습니다, 건너뜁니다")
            continue
            
        if 'parsed_sql' not in item:
            logger.warning(f"항목 {i}: 'parsed_sql' 키가 없습니다, 건너뜁니다")
            continue
        
        validated_items.append({
            'sql': str(item['sql']).strip(),
            'parsed_sql': str(item['parsed_sql']).strip(),
            'index': i,
            'metadata': {k: v for k, v in item.items() if k not in ('sql', 'parsed_sql')}
        })
    
    logger.info(f"총 {len(validated_items)}개 SQL 항목 로드됨")
    return validated_items


def validate_yaml_structure(path: str) -> Optional[str]:
    """
    YAML 파일 구조가 올바른지 미리 검증합니다.
    
    Args:
        path: YAML 파일 경로
        
    Returns:
        오류 메시지 (None이면 유효함)
    """
    try:
        load_yaml(path)
        return None
    except FileNotFoundError as e:
        return str(e)
    except yaml.YAMLError as e:
        return f"YAML 파싱 오류: {e}"
    except ValueError as e:
        return str(e)
