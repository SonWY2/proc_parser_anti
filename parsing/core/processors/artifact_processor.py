"""
아티팩트 프로세서

OMM/DBIO/DAO 아티팩트 생성을 담당합니다.
"""
import os
import re
from typing import Dict, List, Any, Optional

try:
    from ..processor_interface import MetadataProcessor
except ImportError:
    from parsing.core.processor_interface import MetadataProcessor

# OMM/DBIO/DAO 생성기
try:
    from generation.artifacts import OMMGenerator, DBIOGenerator, DAOGenerator
except ImportError:
    OMMGenerator = None
    DBIOGenerator = None
    DAOGenerator = None

# infra.config
try:
    from infra.config import ArtifactConfig
except ImportError:
    ArtifactConfig = None


class ArtifactProcessor(MetadataProcessor):
    """
    아티팩트 생성을 담당하는 프로세서
    
    기능:
    - Header 구조체 OMM 생성
    - SQL Input/Output OMM 생성
    - ContextVO OMM 생성 (전역변수)
    - DBIO (XML) 생성
    - DAO (Java Interface) 생성
    """
    
    def __init__(self, base_package: str = "com.example.dao"):
        """
        Args:
            base_package: 기본 Java 패키지
        """
        self.base_package = base_package
    
    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        아티팩트 생성 수행
        
        Args:
            context:
                - db_vars_info: 헤더 구조체 정보
                - sql_elements: SQL 요소 목록
                - global_variables: 전역변수 목록
                - source_file_name: 소스 파일 경로
                - artifact_config: ArtifactConfig 인스턴스 (선택)
                
        Returns:
            - artifacts: 생성된 아티팩트 딕셔너리
        """
        db_vars_info = context.get('db_vars_info', {})
        sql_elements = context.get('sql_elements', [])
        global_variables = context.get('global_variables', [])
        source_file_name = context.get('source_file_name', '')
        config = context.get('artifact_config')
        
        return {
            "artifacts": self._generate_artifacts(
                db_vars_info,
                sql_elements,
                global_variables,
                source_file_name,
                config
            )
        }
    
    def _generate_artifacts(
        self, 
        db_vars_info: Dict, 
        sql_elements: List[Dict],
        global_variables: List[Dict] = None,
        source_file_name: str = "",
        config: Any = None
    ) -> Dict:
        """OMM/DBIO/DAO 아티팩트 생성
        
        Args:
            db_vars_info: 헤더 파일의 구조체 정보
            sql_elements: SQL 요소 목록
            global_variables: 전역 변수 목록 (ContextVO 생성용)
            source_file_name: 소스 파일명 (ContextVO 클래스명 생성용)
            config: ArtifactConfig 인스턴스
        """
        artifacts = {}
        
        # 0. 설정 결정
        file_id = os.path.splitext(os.path.basename(source_file_name))[0] if source_file_name else "default"
        
        # Config 설정 (없으면 기본값)
        if config is None and ArtifactConfig:
            config = ArtifactConfig(id=file_id, base_package=self.base_package)
        elif config is None:
            # Fallback
            return {}

        # 패키지 및 이름 설정
        dto_package = config.get_dto_package()
        dao_package = config.get_dao_package()
        dao_name = config.get_dao_name()
        dto_prefix = config.dto_prefix or ""
        context_vo_name = config.context_vo_name
        
        # 생성기 인스턴스화
        omm_gen = OMMGenerator(base_package=dto_package) if OMMGenerator else None
        dbio_gen = DBIOGenerator(base_package=dao_package, datasource=config.datasource) if DBIOGenerator else None
        dao_gen = DAOGenerator(base_package=dao_package) if DAOGenerator else None
        
        # 1. Header 구조체 OMM 생성
        if omm_gen and db_vars_info:
            omm_artifacts = {}
            for struct_name, struct_info in db_vars_info.items():
                try:
                    content = omm_gen.generate(struct_info, struct_name)
                    omm_artifacts[struct_name] = {
                        "content": content,
                        "class_name": struct_name.replace('_t', '').title().replace('_', ''),
                        "package": dto_package,
                        "source": "header_struct"
                    }
                except Exception as e:
                    omm_artifacts[struct_name] = {"error": str(e)}
            artifacts["omm"] = omm_artifacts
        else:
            artifacts["omm"] = {}
        
        # 2. SQL Input/Output OMM 생성
        if omm_gen and sql_elements:
            sql_omm_artifacts = {}
            for sql in sql_elements:
                sql_id = sql.get('sql_id', '')
                if not sql_id:
                    continue
                
                # 불필요한 SQL 타입 제외
                if sql.get('mybatis_sql') is None:
                    continue
                
                input_vars = sql.get('input_host_vars', [])
                output_vars = sql.get('output_host_vars', [])
                
                # Input OMM 생성 ({SqlId}In)
                base_name = dto_prefix + self._get_base_name_from_sql(sql_id, sql)
                
                if input_vars:
                    in_class_name = base_name + "In"
                    in_db_vars = self._vars_to_db_vars_info(input_vars, sql)
                    try:
                        content = omm_gen.generate(in_db_vars, in_class_name)
                        sql_omm_artifacts[in_class_name] = {
                            "content": content,
                            "class_name": in_class_name,
                            "package": dto_package,
                            "source": "sql_input",
                            "sql_id": sql_id,
                            "sql_type": sql.get('sql_type')
                        }
                        
                        # SQL 요소에 매핑 정보 추가
                        if 'omm_info' not in sql:
                            sql['omm_info'] = {}
                        sql['omm_info']['input_omm_class'] = in_class_name
                        sql['omm_info']['input_omm_package'] = dto_package
                        
                    except Exception as e:
                        sql_omm_artifacts[in_class_name] = {"error": str(e)}
                
                # Output OMM 생성 ({SqlId}Out)
                if output_vars:
                    out_class_name = base_name + "Out"
                    out_db_vars = self._vars_to_db_vars_info(output_vars, sql)
                    try:
                        content = omm_gen.generate(out_db_vars, out_class_name)
                        sql_omm_artifacts[out_class_name] = {
                            "content": content,
                            "class_name": out_class_name,
                            "package": dto_package,
                            "source": "sql_output",
                            "sql_id": sql_id,
                            "sql_type": sql.get('sql_type')
                        }
                        
                        # SQL 요소에 매핑 정보 추가
                        if 'omm_info' not in sql:
                            sql['omm_info'] = {}
                        sql['omm_info']['output_omm_class'] = out_class_name
                        sql['omm_info']['output_omm_package'] = dto_package
                        
                    except Exception as e:
                        sql_omm_artifacts[out_class_name] = {"error": str(e)}
            
            if sql_omm_artifacts:
                artifacts["omm"].update(sql_omm_artifacts)
        
        # 3. ContextVO OMM 생성 (전역변수만)
        if omm_gen and global_variables:
            # 전역변수만 필터링 (function이 None이거나 scope가 global인 것)
            global_only = [
                v for v in global_variables 
                if v.get('function') is None or v.get('scope') == 'global'
            ]
            
            if global_only:
                # 소스 파일명에서 클래스명 생성
                if context_vo_name:
                    context_class_name = context_vo_name
                elif source_file_name:
                    base_name = os.path.splitext(os.path.basename(source_file_name))[0]
                    context_class_name = self._to_pascal_case(base_name) + "ContextVO"
                else:
                    context_class_name = "ContextVO"
                
                context_db_vars = self._global_vars_to_db_vars_info(global_only)
                try:
                    content = omm_gen.generate(
                        context_db_vars, 
                        context_class_name,
                        logical_name=f"{context_class_name} - 전역변수",
                        description=f"소스 파일 전역변수 ({len(global_only)}개)"
                    )
                    artifacts["omm"][context_class_name] = {
                        "content": content,
                        "class_name": context_class_name,
                        "package": dto_package,
                        "source": "context_vo",
                        "variable_count": len(global_only)
                    }
                except Exception as e:
                    artifacts["omm"][context_class_name] = {"error": str(e)}
        
        # DBIO (XML) & DAO (Java) 생성
        if dbio_gen and dao_gen and sql_elements:
            try:
                # SQL 요소를 변환
                sql_calls = []
                # DTO 매핑 정보 생성 (For DBIO/DAO)
                id_to_path_map = {}
                
                for i, sql in enumerate(sql_elements):
                    sql_id = sql.get('sql_id', f'sql_{i+1}')
                    sql_calls.append({
                        "name": sql_id,
                        "sql_type": sql.get('sql_type', 'select').lower(),
                        "parsed_sql": sql.get('normalized_sql', sql.get('raw_sql', '')),
                        "input_vars": sql.get('input_host_vars', []),
                        "output_vars": sql.get('output_host_vars', [])
                    })
                    
                    # DTO 경로 매핑 (artifacts OMM 정보 등에서 가져옴)
                    if 'omm_info' in sql:
                        if 'input_omm_class' in sql['omm_info']:
                            id_to_path_map[f"{sql_id}In"] = f"{dto_package}.{sql['omm_info']['input_omm_class']}"
                        if 'output_omm_class' in sql['omm_info']:
                            id_to_path_map[f"{sql_id}Out"] = f"{dto_package}.{sql['omm_info']['output_omm_class']}"
                
                # DBIO 생성
                dbio_content = dbio_gen.generate(sql_calls, id_to_path_map, dao_name)
                artifacts["dbio"] = {
                    "content": dbio_content,
                    "namespace": f"{dao_package}.{dao_name}"
                }
                
                # DAO 생성
                dao_content = dao_gen.generate(sql_calls, id_to_path_map, dao_name)
                artifacts["dao"] = {
                    "content": dao_content,
                    "interface_name": dao_name,
                    "package": dao_package
                }
                
            except Exception as e:
                artifacts["dbio"] = {"error": str(e)}
                artifacts["dao"] = {"error": str(e)}
        
        return artifacts
    
    def _get_base_name_from_sql(self, sql_id: str, sql_info: Dict) -> str:
        """SQL ID와 타입에서 적절한 기본 이름 생성 (예: Select003)"""
        sql_type = sql_info.get('sql_type', 'Sql').capitalize()
        
        # ID에서 숫자 추출 (Sql003 -> 003)
        match = re.search(r'(\d+)$', sql_id)
        if match:
            number = match.group(1)
            return f"{sql_type}{number}"
        
        # 숫자가 없으면 ID 활용 (SqlMyQuery -> SelectMyQuery)
        clean_id = self._to_pascal_case(sql_id)
        if clean_id.startswith('Sql'):
            clean_id = clean_id[3:]
            
        return f"{sql_type}{clean_id}"
    
    def _to_pascal_case(self, name: str) -> str:
        """snake_case를 PascalCase로 변환"""
        if not name:
            return ""
        components = name.replace('-', '_').split('_')
        return ''.join(x.title() for x in components)
    
    def _vars_to_db_vars_info(self, var_names: List[str], sql_context: Dict) -> Dict:
        """호스트 변수 목록을 db_vars_info 형식으로 변환
        
        Args:
            var_names: 호스트 변수명 목록 (예: [':acnt_id', ':acnt_no'])
            sql_context: SQL 정보 (추가 컨텍스트용)
        
        Returns:
            db_vars_info 형식의 딕셔너리
        """
        result = {}
        for var_name in var_names:
            # 콜론 제거
            clean_name = var_name.lstrip(':').strip()
            # camelCase로 변환
            camel_name = self._snake_to_camel(clean_name)
            
            result[camel_name] = {
                "dtype": "String",  # 기본 타입 (실제로는 변수 정의에서 추론해야 함)
                "size": 100,
                "decimal": 0,
                "description": clean_name
            }
        return result
    
    def _global_vars_to_db_vars_info(self, variables: List[Dict]) -> Dict:
        """전역변수 목록을 db_vars_info 형식으로 변환
        
        Args:
            variables: 변수 요소 목록
        
        Returns:
            db_vars_info 형식의 딕셔너리
        """
        result = {}
        for var in variables:
            var_name = var.get('name', '')
            if not var_name:
                continue
            
            camel_name = self._snake_to_camel(var_name)
            c_type = var.get('data_type', 'char')
            array_sizes = var.get('resolved_array_sizes') or var.get('array_sizes', [])
            comment = var.get('comment', '')
            
            # C 타입 → Java 타입 및 사이즈 결정
            java_type, size, decimal = self._c_type_to_omm_info(c_type, array_sizes)
            
            result[camel_name] = {
                "dtype": java_type,
                "size": size,
                "decimal": decimal,
                "description": comment or var_name
            }
        return result
    
    def _snake_to_camel(self, name: str) -> str:
        """snake_case를 camelCase로 변환"""
        components = name.split('_')
        return components[0].lower() + ''.join(x.title() for x in components[1:])
    
    def _c_type_to_omm_info(self, c_type: str, array_sizes: List = None) -> tuple:
        """C 타입을 OMM 정보로 변환
        
        Returns:
            (java_type, size, decimal)
        """
        c_type_lower = c_type.lower().strip()
        
        # 배열 사이즈 결정
        if array_sizes:
            try:
                size = int(array_sizes[0])
            except (ValueError, TypeError):
                size = 100
        else:
            size = 9
        
        # 타입 매핑
        if 'char' in c_type_lower:
            return ("String", size, 0)
        elif 'double' in c_type_lower:
            return ("BigDecimal", 18, 6)
        elif 'float' in c_type_lower:
            return ("BigDecimal", 12, 4)
        elif 'long' in c_type_lower:
            return ("Long", 18, 0)
        elif 'int' in c_type_lower:
            return ("Integer", 9, 0)
        elif 'short' in c_type_lower:
            return ("Short", 5, 0)
        else:
            return ("String", size, 0)
