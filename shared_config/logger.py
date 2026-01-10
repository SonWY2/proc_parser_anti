"""
Loguru 기반 로깅 시스템
파일/함수/라인 정보를 포함한 VSCode 클릭 가능 포맷
"""
import sys
import os
from pathlib import Path
from loguru import logger

# 기본 로거 제거 (중복 방지)
logger.remove()

# =============================================================================
# 포맷 설정
# =============================================================================

# 콘솔용 포맷 (컬러 + VSCode 클릭 가능 - file.path:line 형식)
CONSOLE_FORMAT = (
    "<green>{time:HH:mm:ss}</green> | "
    "<level>{level: <7}</level> | "
    "<cyan>{file.path}</cyan>:<cyan>{line}</cyan> in <cyan>{function}()</cyan> | "
    "<level>{message}</level>"
)

# 파일용 포맷 (플레인 텍스트 + VSCode 클릭 가능)
FILE_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss} | "
    "{level: <7} | "
    "{file.path}:{line} in {function}() | "
    "{message}"
)

# =============================================================================
# 콘솔 로깅 설정
# =============================================================================

# 기본 콘솔 핸들러 추가
logger.add(
    sys.stderr,
    format=CONSOLE_FORMAT,
    level="DEBUG",
    colorize=True,
)


# =============================================================================
# 파일 로깅 함수
# =============================================================================

def setup_file_logging(
    log_dir: str = "./logs",
    level: str = "DEBUG",
    rotation: str = "1 day",
    retention: str = "7 days"
):
    """
    파일 로깅 설정
    
    Args:
        log_dir: 로그 디렉토리 경로
        level: 로그 레벨
        rotation: 로테이션 주기
        retention: 보관 기간
        
    Returns:
        추가된 핸들러 ID
    """
    # 디렉토리 생성
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    
    # 파일 핸들러 추가
    handler_id = logger.add(
        str(log_path / "{time:YYYY-MM-DD}_session.log"),
        format=FILE_FORMAT,
        level=level,
        rotation=rotation,
        retention=retention,
        encoding="utf-8",
    )
    
    logger.info(f"파일 로깅 시작: {log_path}")
    return handler_id


def get_logger(module_name: str = None):
    """
    모듈별 로거 반환
    
    Args:
        module_name: 모듈 이름 (None이면 기본 로거)
        
    Returns:
        로거 인스턴스
        
    사용 예:
        logger = get_logger("header_parser")
        logger.info("파싱 시작")
    """
    if module_name:
        return logger.bind(module=module_name)
    return logger


# =============================================================================
# 단계 추적 컨텍스트 매니저
# =============================================================================

class LogStage:
    """
    단계 추적 컨텍스트 매니저
    
    사용 예:
        with LogStage("헤더 파싱", file="sample.h"):
            # 작업 수행
            pass
    """
    
    def __init__(self, stage_name: str, **context):
        self.stage_name = stage_name
        self.context = context
    
    def __enter__(self):
        context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
        if context_str:
            logger.info(f"[시작] {self.stage_name} ({context_str})")
        else:
            logger.info(f"[시작] {self.stage_name}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            logger.error(f"[실패] {self.stage_name}: {exc_val}")
        else:
            logger.success(f"[완료] {self.stage_name}")
        return False


# =============================================================================
# 편의 함수
# =============================================================================

def log_step(step_name: str):
    """단계 로깅 데코레이터"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            logger.info(f"[단계] {step_name}")
            try:
                result = func(*args, **kwargs)
                logger.success(f"[완료] {step_name}")
                return result
            except Exception as e:
                logger.error(f"[실패] {step_name}: {e}")
                raise
        return wrapper
    return decorator


# 모듈 로거 export
__all__ = [
    "logger",
    "get_logger",
    "setup_file_logging",
    "LogStage",
    "log_step",
    "CONSOLE_FORMAT",
    "FILE_FORMAT",
]
