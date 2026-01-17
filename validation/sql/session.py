"""
세션 관리 모듈

작업 상태를 저장하고 복원하는 기능을 제공합니다.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict, field
from loguru import logger


@dataclass
class SessionData:
    """세션 데이터"""
    yaml_path: str = ""
    current_index: int = 0
    validation_statuses: Dict[int, str] = field(default_factory=dict)
    comments: Dict[int, str] = field(default_factory=dict)
    custom_prompt: str = ""
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


def save_session(data: SessionData, path: str) -> bool:
    """
    세션을 파일로 저장합니다.
    
    Args:
        data: SessionData 객체
        path: 저장 경로
        
    Returns:
        성공 여부
    """
    try:
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # int 키를 문자열로 변환 (JSON 호환)
        save_data = asdict(data)
        save_data['validation_statuses'] = {
            str(k): v for k, v in data.validation_statuses.items()
        }
        save_data['comments'] = {
            str(k): v for k, v in data.comments.items()
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"세션 저장됨: {path}")
        return True
        
    except Exception as e:
        logger.error(f"세션 저장 실패: {e}")
        return False


def load_session(path: str) -> Optional[SessionData]:
    """
    파일에서 세션을 로드합니다.
    
    Args:
        path: 세션 파일 경로
        
    Returns:
        SessionData 객체 또는 None
    """
    try:
        file_path = Path(path)
        
        if not file_path.exists():
            logger.error(f"세션 파일을 찾을 수 없습니다: {path}")
            return None
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 문자열 키를 int로 변환
        validation_statuses = {
            int(k): v for k, v in data.get('validation_statuses', {}).items()
        }
        comments = {
            int(k): v for k, v in data.get('comments', {}).items()
        }
        
        session = SessionData(
            yaml_path=data.get('yaml_path', ''),
            current_index=data.get('current_index', 0),
            validation_statuses=validation_statuses,
            comments=comments,
            custom_prompt=data.get('custom_prompt', ''),
            timestamp=data.get('timestamp', '')
        )
        
        logger.info(f"세션 로드됨: {path}")
        return session
        
    except json.JSONDecodeError as e:
        logger.error(f"세션 파일 파싱 오류: {e}")
        return None
    except Exception as e:
        logger.error(f"세션 로드 실패: {e}")
        return None


def generate_session_filename() -> str:
    """타임스탬프가 포함된 세션 파일명 생성"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return f"session_{timestamp}.json"
