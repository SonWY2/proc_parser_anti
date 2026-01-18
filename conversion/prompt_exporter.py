"""
프롬프트 내보내기 모듈

생성된 프롬프트를 파일로 저장합니다.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

from .prompt_builder import PromptBuilder
from .types import ConversionConfig, PromptContext


class PromptExporter:
    """
    프롬프트를 파일로 내보내는 클래스
    
    사용 예:
        exporter = PromptExporter(config)
        exporter.export_skeleton_prompt(metadata, "./prompts/skeleton.md")
        exporter.export_function_prompts(metadata, "./prompts/functions/")
        exporter.export_all(metadata, "./prompts/")
    """
    
    def __init__(self, config: Optional[ConversionConfig] = None):
        """
        Args:
            config: 변환 설정 (None이면 기본값 사용)
        """
        self.config = config or ConversionConfig()
        self.prompt_builder = PromptBuilder(self.config)
    
    def export_skeleton_prompt(
        self, 
        metadata: Dict[str, Any], 
        output_path: str
    ) -> str:
        """
        스켈레톤 프롬프트를 파일로 저장
        
        Args:
            metadata: 메타데이터
            output_path: 출력 파일 경로
            
        Returns:
            저장된 파일 경로
        """
        prompt = self.prompt_builder.build_skeleton_prompt(metadata)
        
        # 시스템 프롬프트 + 유저 프롬프트 결합
        full_prompt = self._create_full_prompt(
            "SKELETON",
            self.prompt_builder.get_system_prompt(),
            prompt,
            metadata
        )
        
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(full_prompt)
        
        return str(output_file)
    
    def export_function_prompt(
        self, 
        metadata: Dict[str, Any], 
        function_name: str,
        output_path: str,
        skeleton_context: bool = False
    ) -> str:
        """
        특정 함수의 프롬프트를 파일로 저장
        
        Args:
            metadata: 메타데이터
            function_name: 함수 이름
            output_path: 출력 파일 경로
            skeleton_context: 스켈레톤 컨텍스트 포함 여부
            
        Returns:
            저장된 파일 경로
        """
        # 함수 찾기
        source_analysis = metadata.get("source_analysis", {})
        elements = source_analysis.get("elements_by_type", {})
        functions = elements.get("functions", [])
        
        target_func = None
        for func in functions:
            if func.get("name") == function_name:
                target_func = func
                break
        
        if target_func is None:
            raise ValueError(f"Function '{function_name}' not found in metadata")
        
        # 컨텍스트 생성
        context = PromptContext(
            source_file=metadata.get("metadata", {}).get("source_file", ""),
            metadata=metadata,
            config=self.config,
        )
        
        prompt = self.prompt_builder.build_function_prompt(target_func, context)
        
        # 시스템 프롬프트 + 유저 프롬프트 결합
        full_prompt = self._create_full_prompt(
            f"FUNCTION: {function_name}",
            self.prompt_builder.get_system_prompt(),
            prompt,
            metadata
        )
        
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(full_prompt)
        
        return str(output_file)
    
    def export_function_prompts(
        self, 
        metadata: Dict[str, Any], 
        output_dir: str,
        function_names: Optional[List[str]] = None
    ) -> Dict[str, str]:
        """
        모든 (또는 지정된) 함수의 프롬프트를 파일로 저장
        
        Args:
            metadata: 메타데이터
            output_dir: 출력 디렉토리
            function_names: 저장할 함수 이름 리스트 (None이면 전체)
            
        Returns:
            {함수명: 파일 경로} 딕셔너리
        """
        source_analysis = metadata.get("source_analysis", {})
        elements = source_analysis.get("elements_by_type", {})
        functions = elements.get("functions", [])
        
        # 대상 함수 필터링
        if function_names:
            target_functions = [f for f in functions if f.get("name") in function_names]
        else:
            target_functions = functions
        
        output_dir_path = Path(output_dir)
        output_dir_path.mkdir(parents=True, exist_ok=True)
        
        results = {}
        for func in target_functions:
            func_name = func.get("name", "unknown")
            output_path = output_dir_path / f"{func_name}.md"
            
            try:
                saved_path = self.export_function_prompt(
                    metadata, func_name, str(output_path)
                )
                results[func_name] = saved_path
            except Exception as e:
                results[func_name] = f"Error: {str(e)}"
        
        return results
    
    def export_all(
        self, 
        metadata: Dict[str, Any], 
        output_dir: str
    ) -> Dict[str, Any]:
        """
        스켈레톤 + 모든 함수 프롬프트를 디렉토리에 저장
        
        Args:
            metadata: 메타데이터
            output_dir: 출력 디렉토리
            
        Returns:
            {
                "skeleton": 파일 경로,
                "functions": {함수명: 파일 경로}
            }
        """
        output_dir_path = Path(output_dir)
        output_dir_path.mkdir(parents=True, exist_ok=True)
        
        # 스켈레톤 프롬프트
        skeleton_path = self.export_skeleton_prompt(
            metadata, 
            str(output_dir_path / "00_skeleton.md")
        )
        
        # 함수 프롬프트
        functions_dir = output_dir_path / "functions"
        function_results = self.export_function_prompts(
            metadata, 
            str(functions_dir)
        )
        
        # 인덱스 파일 생성
        index_content = self._create_index(metadata, skeleton_path, function_results)
        index_path = output_dir_path / "README.md"
        with open(index_path, 'w', encoding='utf-8') as f:
            f.write(index_content)
        
        return {
            "index": str(index_path),
            "skeleton": skeleton_path,
            "functions": function_results,
        }
    
    def _create_full_prompt(
        self, 
        title: str,
        system_prompt: str, 
        user_prompt: str,
        metadata: Dict[str, Any]
    ) -> str:
        """전체 프롬프트 문서 생성"""
        source_file = metadata.get("metadata", {}).get("source_file", "unknown")
        generated_at = datetime.now().isoformat()
        
        return f"""# LLM Prompt - {title}

> Generated from: `{source_file}`
> Generated at: {generated_at}

---

## System Prompt

```
{system_prompt}
```

---

## User Prompt

{user_prompt}
"""
    
    def _create_index(
        self, 
        metadata: Dict[str, Any], 
        skeleton_path: str,
        function_results: Dict[str, str]
    ) -> str:
        """인덱스 문서 생성"""
        source_file = metadata.get("metadata", {}).get("source_file", "unknown")
        generated_at = datetime.now().isoformat()
        
        lines = [
            f"# Prompt Export - {source_file}",
            f"\n> Generated at: {generated_at}",
            f"\n## Files",
            f"\n### Skeleton Prompt",
            f"- [{Path(skeleton_path).name}]({Path(skeleton_path).name})",
            f"\n### Function Prompts",
        ]
        
        for func_name, path in sorted(function_results.items()):
            if path.startswith("Error"):
                lines.append(f"- ❌ `{func_name}`: {path}")
            else:
                rel_path = f"functions/{Path(path).name}"
                lines.append(f"- [{func_name}]({rel_path})")
        
        lines.append(f"\n## Statistics")
        lines.append(f"- Total functions: {len(function_results)}")
        errors = sum(1 for p in function_results.values() if p.startswith("Error"))
        lines.append(f"- Errors: {errors}")
        
        return "\n".join(lines)
