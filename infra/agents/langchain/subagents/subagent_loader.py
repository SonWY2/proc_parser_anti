"""
Subagent 로더

.md 파일에서 Subagent 설정을 로드하고 SubagentConfig로 변환합니다.
YAML frontmatter + Markdown 형식을 지원합니다.
"""

import re
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class SubagentConfig:
    """
    Subagent 설정
    
    .md 파일에서 파싱된 Subagent 구성 정보를 담습니다.
    
    Attributes:
        name: Subagent 고유 이름
        persona: 역할 (예: "분해자", "검증자")
        description: 설명
        skills: 사용하는 Skill 이름 목록
        uses_llm: LLM 사용 여부
        system_prompt: LLM용 시스템 프롬프트
        input_fields: State에서 읽는 필드 목록
        output_fields: State에 쓰는 필드 목록
    """
    name: str
    persona: str = ""
    description: str = ""
    skills: List[str] = field(default_factory=list)
    uses_llm: bool = False
    system_prompt: str = ""
    input_fields: List[str] = field(default_factory=list)
    output_fields: List[str] = field(default_factory=list)
    model: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "persona": self.persona,
            "description": self.description,
            "skills": self.skills,
            "uses_llm": self.uses_llm,
            "system_prompt": self.system_prompt,
            "input_fields": self.input_fields,
            "output_fields": self.output_fields,
            "model": self.model,
        }


class SubagentLoader:
    """
    .md 파일에서 Subagent 설정 로드
    
    YAML frontmatter + Markdown 형식의 .md 파일을 파싱합니다.
    
    Example:
        loader = SubagentLoader(Path("subagents/definitions"))
        agents = loader.load_all()
        parser_config = agents["parser_agent"]
    
    MD 파일 형식:
        ---
        name: parser_agent
        persona: 분해자
        skills:
          - parse_proc_code
        uses_llm: false
        input_fields:
          - source_code
        output_fields:
          - ast_data
        ---
        
        # Parser Agent
        
        본문은 system_prompt로 사용됩니다.
    """
    
    # YAML frontmatter 패턴
    FRONTMATTER_PATTERN = re.compile(
        r'^---\s*\n(.*?)\n---\s*\n(.*)$',
        re.DOTALL
    )
    
    def __init__(self, agents_dir: Path = None):
        """
        Args:
            agents_dir: .md 파일이 있는 디렉토리 경로
        """
        if agents_dir is None:
            # 기본 경로: 현재 모듈 위치 기준
            agents_dir = Path(__file__).parent / "definitions"
        
        self.agents_dir = Path(agents_dir)
    
    def load_all(self) -> Dict[str, SubagentConfig]:
        """
        모든 .md 파일에서 Subagent 로드
        
        Returns:
            {name: SubagentConfig} 딕셔너리
        """
        agents = {}
        
        if not self.agents_dir.exists():
            logger.warning(f"Subagent 디렉토리 없음: {self.agents_dir}")
            return agents
        
        for md_file in self.agents_dir.glob("*.md"):
            try:
                config = self.load_one(md_file)
                if config:
                    agents[config.name] = config
                    logger.debug(f"Subagent 로드: {config.name}")
            except Exception as e:
                logger.error(f"Subagent 로드 실패 ({md_file}): {e}")
        
        return agents
    
    def load_one(self, path: Path) -> Optional[SubagentConfig]:
        """
        단일 .md 파일에서 Subagent 로드
        
        Args:
            path: .md 파일 경로
            
        Returns:
            SubagentConfig 또는 None
        """
        content = path.read_text(encoding="utf-8")
        return self._parse_md(content, path.stem)
    
    def _parse_md(self, content: str, default_name: str = "unnamed") -> Optional[SubagentConfig]:
        """
        MD 파일 내용 파싱
        
        Args:
            content: 파일 내용
            default_name: 이름이 없을 경우 기본 이름
            
        Returns:
            SubagentConfig 또는 None
        """
        match = self.FRONTMATTER_PATTERN.match(content)
        
        if not match:
            # Frontmatter가 없으면 전체를 본문으로 취급
            logger.warning(f"YAML frontmatter 없음: {default_name}")
            return SubagentConfig(
                name=default_name,
                system_prompt=content.strip(),
            )
        
        frontmatter_str = match.group(1)
        body = match.group(2).strip()
        
        try:
            frontmatter = yaml.safe_load(frontmatter_str)
        except yaml.YAMLError as e:
            logger.error(f"YAML 파싱 오류: {e}")
            return None
        
        if not isinstance(frontmatter, dict):
            logger.error(f"Frontmatter가 딕셔너리가 아님: {type(frontmatter)}")
            return None
        
        return SubagentConfig(
            name=frontmatter.get("name", default_name),
            persona=frontmatter.get("persona", ""),
            description=frontmatter.get("description", ""),
            skills=frontmatter.get("skills", []),
            uses_llm=frontmatter.get("uses_llm", False),
            system_prompt=body,  # 본문을 system_prompt로 사용
            input_fields=frontmatter.get("input_fields", []),
            output_fields=frontmatter.get("output_fields", []),
            model=frontmatter.get("model"),
        )
    
    def reload(self) -> Dict[str, SubagentConfig]:
        """Subagent 설정 다시 로드"""
        return self.load_all()
