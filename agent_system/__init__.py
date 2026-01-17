"""
agent_system - 에이전트 시스템 (호환성 레이어)

이 모듈은 이전 경로에서의 import를 지원하기 위한 호환성 레이어입니다.
실제 구현은 infra.agents.base 패키지에 있습니다.
"""

from infra.agents.base import *
from infra.agents.base import __all__
