"""
Spring 어노테이션 플러그인

생성된 Java 클래스에 Spring 어노테이션을 추가합니다.
"""

import re
from typing import Dict, Any

from ..plugin_interface import ConversionPlugin
from ..types import (
    ConversionConfig,
    SkeletonResult,
    FunctionConversionResult,
)


class SpringAnnotationPlugin(ConversionPlugin):
    """
    Spring 어노테이션 추가 플러그인
    
    - @Service 클래스 어노테이션
    - @Slf4j 로깅 어노테이션
    - @Autowired 의존성 주입
    - @Transactional 트랜잭션 관리
    """
    
    def post_skeleton(self, result: SkeletonResult, config: ConversionConfig) -> SkeletonResult:
        """스켈레톤 코드에 Spring 어노테이션 추가"""
        
        if not config.use_spring_annotations:
            return result
        
        code = result.java_code
        
        # 이미 어노테이션이 있는지 확인
        if "@Service" in code or "@Component" in code:
            return result
        
        # 클래스 선언 앞에 어노테이션 추가
        class_pattern = r'(public\s+class\s+)'
        if re.search(class_pattern, code):
            annotations = "@Service\n@Slf4j\n"
            code = re.sub(class_pattern, annotations + r'\1', code)
        
        # import 추가
        import_section = """import org.springframework.stereotype.Service;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.transaction.annotation.Transactional;
import lombok.extern.slf4j.Slf4j;
"""
        
        # 기존 import 뒤에 추가
        if "import " in code:
            last_import = code.rfind("import ")
            end_of_import = code.find(";", last_import) + 1
            code = code[:end_of_import] + "\n" + import_section + code[end_of_import:]
        else:
            # package 선언 뒤에 추가
            package_end = code.find(";") + 1
            code = code[:package_end] + "\n\n" + import_section + code[package_end:]
        
        result.java_code = code
        
        # imports 리스트에도 추가
        result.imports.extend([
            "org.springframework.stereotype.Service",
            "org.springframework.beans.factory.annotation.Autowired",
            "org.springframework.transaction.annotation.Transactional",
            "lombok.extern.slf4j.Slf4j",
        ])
        
        return result
    
    def post_function(
        self, 
        result: FunctionConversionResult, 
        config: ConversionConfig
    ) -> FunctionConversionResult:
        """SQL 작업이 포함된 함수에 @Transactional 추가"""
        
        if not config.use_spring_annotations:
            return result
        
        # SQL 참조가 있으면 @Transactional 추가
        if result.sql_references:
            code = result.java_code
            
            # 이미 @Transactional이 있는지 확인
            if "@Transactional" not in code:
                # 메서드 선언 앞에 추가
                method_pattern = r'((?:public|private|protected)\s+\w+\s+\w+\s*\()'
                if re.search(method_pattern, code):
                    code = re.sub(method_pattern, "@Transactional\n    " + r'\1', code)
                    result.java_code = code
        
        return result
