"""
클래스 병합 핵심 로직

LLM이 생성한 클래스 스켈레톤과 개별 메소드들을 하나의 완전한 Java 클래스로 병합.
"""

from typing import List

from .types import MethodTranslation, MergeResult
from .java_parser import JavaParser


class TranslationMerger:
    """Pro*C → Java 변환 결과물 병합 클래스."""
    
    def __init__(self, parser: JavaParser = None):
        """
        Args:
            parser: Java 파서 인스턴스 (None이면 기본 생성)
        """
        self.parser = parser or JavaParser()
    
    def merge(
        self,
        class_skeleton: str,
        method_translations: List[MethodTranslation]
    ) -> MergeResult:
        """클래스 스켈레톤과 메소드들을 병합.
        
        병합 과정:
        1. class_skeleton에서 package, import, class 구조 추출
        2. 각 method_translation에서:
           - 추가 import 수집
           - 지정된 메소드 블럭 추출
        3. import 중복 제거 및 정렬
        4. class 본문에 메소드들 삽입
        5. 최종 코드 조립
        
        Args:
            class_skeleton: LLM이 생성한 클래스 스켈레톤
            method_translations: 메소드 변환 결과 리스트
            
        Returns:
            MergeResult 객체
        """
        warnings = []
        
        # 1. 스켈레톤에서 기본 구조 추출
        package_decl = self.parser.extract_package_declaration(class_skeleton)
        skeleton_imports = self.parser.extract_imports(class_skeleton)
        
        # 2. 각 메소드에서 import와 메소드 추출
        all_imports = skeleton_imports.copy()
        extracted_methods = []
        method_names = []
        
        for translation in method_translations:
            # import 수집
            method_imports = self.parser.extract_imports(translation.llm_response)
            all_imports.extend(method_imports)
            
            # 메소드 추출
            method = self.parser.extract_method_by_name(
                translation.llm_response, 
                translation.name
            )
            
            if method:
                extracted_methods.append(method)
                method_names.append(method.name)
            else:
                warnings.append(f"메소드 '{translation.name}'을(를) 찾을 수 없습니다.")
        
        # 3. import 중복 제거 및 정렬
        unique_imports = self.parser.deduplicate_imports(all_imports)
        
        # 4. 최종 코드 조립
        merged_code = self._assemble_code(
            class_skeleton,
            package_decl,
            unique_imports,
            extracted_methods
        )
        
        return MergeResult(
            merged_code=merged_code,
            imports=[imp.replace('import ', '').replace(';', '').strip() 
                     for imp in unique_imports],
            methods=method_names,
            warnings=warnings
        )
    
    def _assemble_code(
        self,
        skeleton: str,
        package_decl: str,
        imports: List[str],
        methods
    ) -> str:
        """코드 조립.
        
        Args:
            skeleton: 클래스 스켈레톤
            package_decl: package 선언
            imports: 정렬된 import 목록
            methods: ExtractedMethod 리스트
            
        Returns:
            조립된 Java 코드
        """
        # 클래스 본문 삽입 위치 찾기
        insertion_point = self.parser.extract_class_body_insertion_point(skeleton)
        
        if insertion_point == -1:
            # 삽입 위치를 찾지 못한 경우, skeleton 그대로 반환하고 메소드는 끝에 추가
            method_code = '\n\n'.join(m.body for m in methods)
            return skeleton + '\n\n// === 추출된 메소드 ===\n' + method_code
        
        # 스켈레톤에서 import 영역 제거 후 새 import로 교체
        code_without_imports = self._remove_imports(skeleton)
        
        # package 이후에 import 삽입
        if package_decl:
            pkg_end = code_without_imports.find(package_decl) + len(package_decl)
            # package 선언 다음 줄 찾기
            next_newline = code_without_imports.find('\n', pkg_end)
            if next_newline == -1:
                next_newline = pkg_end
            
            before_pkg = code_without_imports[:next_newline + 1]
            after_pkg = code_without_imports[next_newline + 1:]
        else:
            before_pkg = ''
            after_pkg = code_without_imports
        
        # import 블럭 생성
        import_block = '\n'.join(imports)
        if import_block:
            import_block = '\n' + import_block + '\n'
        
        # class 본문 위치 다시 계산 (import 제거 후)
        reconstructed = before_pkg + import_block + after_pkg
        new_insertion_point = self.parser.extract_class_body_insertion_point(reconstructed)
        
        if new_insertion_point == -1:
            method_code = '\n\n'.join(m.body for m in methods)
            return reconstructed + '\n\n// === 추출된 메소드 ===\n' + method_code
        
        # 메소드 코드 생성
        method_code = '\n\n'.join('    ' + self._indent_method(m.body) for m in methods)
        if method_code:
            method_code = '\n' + method_code + '\n'
        
        # 최종 조립
        before_close = reconstructed[:new_insertion_point]
        after_close = reconstructed[new_insertion_point:]
        
        return before_close + method_code + after_close
    
    def _remove_imports(self, code: str) -> str:
        """코드에서 import 구문 제거.
        
        Args:
            code: 원본 코드
            
        Returns:
            import가 제거된 코드
        """
        import re
        # import 구문이 있는 줄 전체 제거
        result = re.sub(
            r'^\s*import\s+(static\s+)?[a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*(?:\.\*)?\s*;\s*\n?',
            '',
            code,
            flags=re.MULTILINE
        )
        return result
    
    def _indent_method(self, method_body: str) -> str:
        """메소드 본문에 기본 들여쓰기 적용.
        
        첫 줄은 들여쓰기 없이, 나머지 줄은 4칸 들여쓰기.
        
        Args:
            method_body: 메소드 코드
            
        Returns:
            들여쓰기가 적용된 코드
        """
        lines = method_body.split('\n')
        if not lines:
            return method_body
        
        # 첫 줄은 그대로, 나머지는 4칸 추가 들여쓰기
        result = [lines[0]]
        for line in lines[1:]:
            if line.strip():  # 빈 줄이 아닌 경우만
                result.append('    ' + line)
            else:
                result.append(line)
        
        return '\n'.join(result)
