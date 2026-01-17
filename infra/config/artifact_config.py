from dataclasses import dataclass, field
from typing import Dict, Optional, List
import json
import os

@dataclass
class ArtifactConfig:
    """Artifact generation configuration for a specific source file"""
    id: str  # Source file name (without extension)
    base_package: str = "com.example.dao"
    dto_package: Optional[str] = None
    dao_package: Optional[str] = None
    dao_name: Optional[str] = None
    dto_prefix: Optional[str] = None
    datasource: str = "MainDS"
    context_vo_name: Optional[str] = None
    
    def get_dto_package(self) -> str:
        return self.dto_package or f"{self.base_package}.dto"
    
    def get_dao_package(self) -> str:
        return self.dao_package or self.base_package
    
    def get_dao_name(self, default: str = "GeneratedDao") -> str:
        return self.dao_name or default

class ArtifactConfigLoader:
    """Loader for artifact configuration from JSONL files"""
    
    @staticmethod
    def load(file_path: str) -> Dict[str, ArtifactConfig]:
        """
        Load artifact configurations from a JSONL file.
        
        Args:
            file_path: Path to the JSONL file
            
        Returns:
            Dictionary mapping source ID (filename) to ArtifactConfig
        """
        configs = {}
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Configuration file not found: {file_path}")
            
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                    
                try:
                    data = json.loads(line)
                    if 'id' not in data:
                        # Log warning or error? For now, skip or raise
                        continue
                        
                    config = ArtifactConfig(
                        id=data['id'],
                        base_package=data.get('base_package', "com.example.dao"),
                        dto_package=data.get('dto_package'),
                        dao_package=data.get('dao_package'),
                        dao_name=data.get('dao_name'),
                        dto_prefix=data.get('dto_prefix'),
                        datasource=data.get('datasource', "MainDS"),
                        context_vo_name=data.get('context_vo_name')
                    )
                    configs[config.id] = config
                except json.JSONDecodeError as e:
                    print(f"Warning: Failed to parse JSON at line {line_num}: {e}")
                    
        return configs
    
    @staticmethod
    def get_config(configs: Dict[str, ArtifactConfig], source_id: str) -> ArtifactConfig:
        """
        Get configuration for a specific source ID.
        Returns a default configuration if not found.
        """
        if source_id in configs:
            return configs[source_id]
            
        # Default fallback
        return ArtifactConfig(id=source_id)
