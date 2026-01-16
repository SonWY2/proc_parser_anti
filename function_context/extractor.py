"""
함수 컨텍스트 추출기

특정 함수에 대한 모든 관련 정보(SQL, 변수, 매크로, 구조체, 아티팩트)를 추출합니다.
"""
from typing import Dict, List, Optional

from .types import FunctionContext
from .indexer import MetadataIndexer
from .artifact_generator import FunctionArtifactGenerator


class FunctionContextExtractor:
    """
    함수별 컨텍스트 추출기
    
    UnifiedMetadataGenerator의 출력에서 특정 함수와 관련된 모든 정보를 추출합니다.
    
    사용 예시:
        >>> from function_context import FunctionContextExtractor
        >>> extractor = FunctionContextExtractor(metadata)
        >>> ctx = extractor.extract("process_data", include_sql=True, include_mybatis=True)
        >>> print(ctx.sql)
        >>> print(ctx.mybatis_xml)
    """
    
    def __init__(
        self, 
        metadata: Dict,
        base_package: str = "com.example"
    ):
        """
        Args:
            metadata: UnifiedMetadataGenerator.generate() 출력
            base_package: 아티팩트 생성 시 Java 패키지명
        """
        self.metadata = metadata
        self.base_package = base_package
        
        # 인덱서 및 아티팩트 생성기 초기화
        self._indexer = MetadataIndexer(metadata)
        self._artifact_gen = FunctionArtifactGenerator(base_package=base_package)
    
    def list_functions(self) -> List[str]:
        """
        메타데이터에 있는 모든 함수 목록 반환
        
        Returns:
            함수명 리스트
        """
        return self._indexer.list_functions()
    
    def extract(
        self,
        function_name: str,
        include_sql: bool = True,
        include_variables: bool = True,
        include_macros: bool = True,
        include_structs: bool = True,
        include_mybatis: bool = False,
        include_omm: bool = False,
        include_dbio: bool = False,
        include_dao: bool = False,
    ) -> FunctionContext:
        """
        특정 함수의 컨텍스트 추출
        
        Args:
            function_name: 추출할 함수명
            include_sql: SQL 포함 여부
            include_variables: 변수 포함 여부
            include_macros: 매크로 포함 여부
            include_structs: 구조체 포함 여부
            include_mybatis: MyBatis XML 생성 여부
            include_omm: OMM VO 클래스 생성 여부
            include_dbio: DBIO 클래스 생성 여부
            include_dao: DAO 인터페이스 생성 여부
            
        Returns:
            FunctionContext 객체
        """
        func_info = self._indexer.get_function_info(function_name)
        
        if not func_info:
            # 함수를 찾지 못한 경우 빈 컨텍스트 반환
            return FunctionContext(name=function_name)
        
        # 기본 함수 정보로 컨텍스트 초기화
        ctx = FunctionContext(
            name=function_name,
            line_start=func_info.line_start,
            line_end=func_info.line_end,
            return_type=func_info.return_type,
            parameters=func_info.parameters,
        )
        
        # 함수의 raw_content 찾기
        elements = self.metadata.get("elements", {})
        for func in elements.get("functions", []):
            if func.get("name") == function_name:
                ctx.raw_content = func.get("raw_content", "")
                break
        
        # SQL 추출
        if include_sql:
            ctx.sql = self._indexer.get_sql_for_function(function_name)
        
        # 변수 추출
        if include_variables:
            ctx.local_variables = self._indexer.get_local_variables(function_name)
            ctx.used_global_variables = self._indexer.find_used_global_vars_in_function(function_name)
        
        # 매크로 추출
        if include_macros:
            ctx.used_macros = self._indexer.find_used_macros_in_function(function_name)
        
        # 구조체 추출
        if include_structs:
            ctx.used_structs = self._indexer.find_used_structs_in_function(function_name)
        
        # 아티팩트 생성
        if include_mybatis and ctx.sql:
            namespace = f"{self.base_package}.mapper.{function_name}"
            ctx.mybatis_xml = self._artifact_gen.generate_mybatis_xml(ctx.sql, namespace)
        
        if include_omm:
            all_vars = ctx.local_variables + ctx.used_global_variables
            if all_vars:
                ctx.omm_code = self._artifact_gen.generate_omm(function_name, all_vars)
        
        if include_dbio and ctx.sql:
            ctx.dbio_code = self._artifact_gen.generate_dbio(function_name, ctx.sql)
        
        if include_dao and ctx.sql:
            ctx.dao_code = self._artifact_gen.generate_dao(function_name, ctx.sql)
        
        return ctx
    
    def extract_all(
        self,
        include_sql: bool = True,
        include_variables: bool = True,
        include_macros: bool = True,
        include_structs: bool = True,
        include_mybatis: bool = False,
        include_omm: bool = False,
        include_dbio: bool = False,
        include_dao: bool = False,
    ) -> Dict[str, FunctionContext]:
        """
        모든 함수의 컨텍스트 추출
        
        Args:
            (extract와 동일)
            
        Returns:
            함수명 → FunctionContext 딕셔너리
        """
        result = {}
        
        for func_name in self.list_functions():
            result[func_name] = self.extract(
                func_name,
                include_sql=include_sql,
                include_variables=include_variables,
                include_macros=include_macros,
                include_structs=include_structs,
                include_mybatis=include_mybatis,
                include_omm=include_omm,
                include_dbio=include_dbio,
                include_dao=include_dao,
            )
        
        return result
    
    def get_function_summary(self, function_name: str) -> str:
        """
        함수의 간단한 요약 정보 반환
        
        Args:
            function_name: 함수명
            
        Returns:
            요약 문자열
        """
        ctx = self.extract(
            function_name,
            include_sql=True,
            include_variables=True,
            include_macros=True,
            include_structs=True,
        )
        return ctx.summary()
    
    def export_function_json(
        self,
        function_name: str,
        output_path: str,
        **extract_options
    ):
        """
        특정 함수의 컨텍스트를 JSON 파일로 저장
        
        Args:
            function_name: 함수명
            output_path: 출력 파일 경로
            **extract_options: extract() 메서드 옵션
        """
        ctx = self.extract(function_name, **extract_options)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(ctx.to_json())
    
    def export_all_json(
        self,
        output_path: str,
        **extract_options
    ):
        """
        모든 함수의 컨텍스트를 JSON 파일로 저장
        
        Args:
            output_path: 출력 파일 경로
            **extract_options: extract() 메서드 옵션
        """
        import json
        
        all_contexts = self.extract_all(**extract_options)
        
        result = {
            name: ctx.to_dict()
            for name, ctx in all_contexts.items()
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
