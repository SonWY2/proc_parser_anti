"""
플러그인 레지스트리 및 자동 로더

plugins 폴더 내 모든 플러그인을 자동으로 검색하고 등록.
"""

import importlib
import pkgutil
from pathlib import Path
from typing import Dict, List, Optional, Type

from .base import VerifierPlugin, PluginPhase


# 플러그인 레지스트리
_registry: Dict[str, Type[VerifierPlugin]] = {}


def register_plugin(cls: Type[VerifierPlugin]) -> Type[VerifierPlugin]:
    """플러그인 등록 데코레이터
    
    사용 예:
        @register_plugin
        class MyPlugin(VerifierPlugin):
            name = "my_plugin"
            ...
    
    Args:
        cls: 등록할 플러그인 클래스
        
    Returns:
        등록된 플러그인 클래스 (데코레이터 체이닝 지원)
    """
    if not issubclass(cls, VerifierPlugin):
        raise TypeError(f"{cls.__name__}은(는) VerifierPlugin을 상속해야 합니다.")
    
    if cls.name in _registry:
        raise ValueError(f"플러그인 이름 '{cls.name}'이(가) 이미 등록되어 있습니다.")
    
    _registry[cls.name] = cls
    return cls


def get_plugin(name: str) -> Type[VerifierPlugin]:
    """이름으로 플러그인 클래스 조회
    
    Args:
        name: 플러그인 이름
        
    Returns:
        플러그인 클래스
        
    Raises:
        KeyError: 플러그인을 찾을 수 없는 경우
    """
    if name not in _registry:
        raise KeyError(f"플러그인 '{name}'을(를) 찾을 수 없습니다.")
    return _registry[name]


def list_plugins() -> List[str]:
    """등록된 모든 플러그인 이름 반환
    
    Returns:
        플러그인 이름 리스트
    """
    return list(_registry.keys())


def load_plugins(names: Optional[List[str]] = None) -> List[VerifierPlugin]:
    """플러그인 인스턴스 로드
    
    Args:
        names: 로드할 플러그인 이름 리스트 (None이면 전체 로드)
        
    Returns:
        priority 순으로 정렬된 플러그인 인스턴스 리스트
    """
    if names is None:
        plugins = [cls() for cls in _registry.values()]
    else:
        plugins = [_registry[name]() for name in names if name in _registry]
    
    # priority 순 정렬 (낮을수록 먼저)
    return sorted(plugins, key=lambda p: p.priority)


def load_plugins_by_phase(
    phase: PluginPhase,
    stage: str = "all",
    names: Optional[List[str]] = None
) -> List[VerifierPlugin]:
    """특정 phase와 stage의 플러그인만 로드
    
    Args:
        phase: 실행 시점 (PRE_VERIFY, VERIFY, POST_VERIFY)
        stage: 검증 단계 ("sql_extraction", "all" 등)
        names: 로드할 플러그인 이름 리스트 (None이면 전체)
        
    Returns:
        해당 phase/stage의 플러그인 인스턴스 리스트 (priority 순)
    """
    all_plugins = load_plugins(names)
    
    filtered = []
    for p in all_plugins:
        # phase 일치 확인
        if p.phase != phase:
            continue
        
        # stage 일치 확인 ("all"이면 모든 stage에 적용)
        if p.stage != "all" and p.stage != stage:
            continue
        
        filtered.append(p)
    
    return filtered


def _discover_plugins():
    """plugins 폴더 내 모든 플러그인 모듈 자동 임포트
    
    이 함수는 모듈 로드 시 자동 호출됨.
    """
    package_dir = Path(__file__).parent
    
    for module_info in pkgutil.iter_modules([str(package_dir)]):
        if module_info.name.startswith('_') or module_info.name == 'base':
            continue
        
        # 모듈 임포트 (register_plugin 데코레이터가 자동 실행됨)
        importlib.import_module(f".{module_info.name}", package=__package__)


# 모듈 로드 시 플러그인 자동 검색
_discover_plugins()


__all__ = [
    'VerifierPlugin',
    'PluginPhase',
    'register_plugin',
    'get_plugin',
    'list_plugins',
    'load_plugins',
    'load_plugins_by_phase',
]
