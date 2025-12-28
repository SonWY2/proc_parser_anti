"""
파일 기반 에이전트 간 통신

에이전트들은 독립된 컨텍스트를 가지므로,
마크다운 파일을 매개체로 정보를 전달합니다.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime
import time
import json


@dataclass
class IntermediateArtifact:
    """에이전트 간 전달되는 중간 결과물"""
    name: str                           # 예: "FLOW.md", "PARSED.md"
    created_by: str                     # 생성한 에이전트
    consumed_by: List[str] = field(default_factory=list)  # 사용할 에이전트들
    path: Optional[str] = None          # 파일 경로 (None이면 자동 생성)
    schema: Optional[str] = None        # 예상 형식 설명
    created_at: Optional[str] = None
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


@dataclass 
class ArtifactStatus:
    """중간 결과물 상태"""
    exists: bool
    path: str
    size: int = 0
    modified_at: Optional[str] = None
    content_preview: str = ""


class FileMediator:
    """
    파일 매개체 관리자
    
    에이전트 간 전달되는 파일을 추적하고 검증합니다.
    """
    
    DEFAULT_DIR = ".workflow_artifacts"
    
    def __init__(self, workspace_dir: Optional[str] = None):
        self.workspace = Path(workspace_dir or ".") / self.DEFAULT_DIR
        self.artifacts: Dict[str, IntermediateArtifact] = {}
        self._ensure_workspace()
    
    def _ensure_workspace(self) -> None:
        """워크스페이스 디렉토리 생성"""
        self.workspace.mkdir(parents=True, exist_ok=True)
    
    def register_artifact(self, artifact: IntermediateArtifact) -> str:
        """
        중간 결과물 등록
        
        Returns:
            실제 파일 경로
        """
        if not artifact.path:
            artifact.path = str(self.workspace / artifact.name)
        
        self.artifacts[artifact.name] = artifact
        return artifact.path
    
    def get_path(self, name: str) -> Optional[str]:
        """아티팩트 경로 조회"""
        artifact = self.artifacts.get(name)
        return artifact.path if artifact else None
    
    def check_ready(self, artifact_name: str) -> bool:
        """파일이 준비되었는지 확인"""
        artifact = self.artifacts.get(artifact_name)
        if not artifact or not artifact.path:
            return False
        return Path(artifact.path).exists()
    
    def get_status(self, artifact_name: str) -> ArtifactStatus:
        """아티팩트 상태 조회"""
        artifact = self.artifacts.get(artifact_name)
        if not artifact or not artifact.path:
            return ArtifactStatus(exists=False, path="")
        
        path = Path(artifact.path)
        if not path.exists():
            return ArtifactStatus(exists=False, path=artifact.path)
        
        stat = path.stat()
        content = ""
        try:
            content = path.read_text(encoding='utf-8')[:500]
        except Exception:
            pass
        
        return ArtifactStatus(
            exists=True,
            path=artifact.path,
            size=stat.st_size,
            modified_at=datetime.fromtimestamp(stat.st_mtime).isoformat(),
            content_preview=content
        )
    
    def wait_for(
        self, 
        artifact_names: List[str], 
        timeout: int = 60,
        poll_interval: float = 1.0
    ) -> Dict[str, bool]:
        """
        여러 파일이 모두 준비될 때까지 대기
        
        Args:
            artifact_names: 대기할 아티팩트 이름들
            timeout: 최대 대기 시간 (초)
            poll_interval: 폴링 간격 (초)
            
        Returns:
            각 아티팩트별 준비 상태
        """
        start_time = time.time()
        results = {name: False for name in artifact_names}
        
        while time.time() - start_time < timeout:
            all_ready = True
            for name in artifact_names:
                if not results[name]:
                    results[name] = self.check_ready(name)
                    if not results[name]:
                        all_ready = False
            
            if all_ready:
                break
            
            time.sleep(poll_interval)
        
        return results
    
    def write_artifact(
        self, 
        name: str, 
        content: str,
        agent_name: str = "unknown"
    ) -> str:
        """
        아티팩트 쓰기
        
        Returns:
            파일 경로
        """
        if name not in self.artifacts:
            artifact = IntermediateArtifact(
                name=name,
                created_by=agent_name
            )
            self.register_artifact(artifact)
        
        path = Path(self.artifacts[name].path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
        
        return str(path)
    
    def read_artifact(self, name: str) -> Optional[str]:
        """아티팩트 읽기"""
        artifact = self.artifacts.get(name)
        if not artifact or not artifact.path:
            return None
        
        path = Path(artifact.path)
        if not path.exists():
            return None
        
        return path.read_text(encoding='utf-8')
    
    def list_artifacts(self) -> List[Dict[str, Any]]:
        """등록된 아티팩트 목록"""
        return [
            {
                "name": a.name,
                "created_by": a.created_by,
                "consumed_by": a.consumed_by,
                "path": a.path,
                "ready": self.check_ready(a.name)
            }
            for a in self.artifacts.values()
        ]
    
    def cleanup(self) -> int:
        """모든 아티팩트 파일 삭제"""
        count = 0
        for artifact in self.artifacts.values():
            if artifact.path:
                path = Path(artifact.path)
                if path.exists():
                    path.unlink()
                    count += 1
        return count
    
    def save_manifest(self) -> str:
        """아티팩트 매니페스트 저장"""
        manifest_path = self.workspace / "manifest.json"
        data = {
            "artifacts": [
                {
                    "name": a.name,
                    "created_by": a.created_by,
                    "consumed_by": a.consumed_by,
                    "path": a.path,
                    "created_at": a.created_at
                }
                for a in self.artifacts.values()
            ]
        }
        manifest_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )
        return str(manifest_path)
    
    def load_manifest(self) -> int:
        """아티팩트 매니페스트 로드"""
        manifest_path = self.workspace / "manifest.json"
        if not manifest_path.exists():
            return 0
        
        data = json.loads(manifest_path.read_text(encoding='utf-8'))
        count = 0
        for item in data.get("artifacts", []):
            artifact = IntermediateArtifact(
                name=item["name"],
                created_by=item["created_by"],
                consumed_by=item.get("consumed_by", []),
                path=item.get("path"),
                created_at=item.get("created_at")
            )
            self.artifacts[artifact.name] = artifact
            count += 1
        
        return count
