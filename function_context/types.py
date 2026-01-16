"""
Function Context 모듈 타입 정의

특정 함수의 컨텍스트 정보를 담는 데이터 클래스들을 정의합니다.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import json


@dataclass
class FunctionContext:
    """
    함수의 컨텍스트 정보를 담는 데이터 클래스
    
    특정 함수와 관련된 모든 코드 요소(SQL, 변수, 매크로, 구조체)와
    선택적으로 생성된 아티팩트(MyBatis, OMM, DBIO, DAO)를 포함합니다.
    """
    # 함수 기본 정보
    name: str
    line_start: int = 0
    line_end: int = 0
    return_type: str = "void"
    parameters: List[str] = field(default_factory=list)
    raw_content: str = ""
    
    # 추출된 코드 요소
    sql: List[Dict] = field(default_factory=list)
    local_variables: List[Dict] = field(default_factory=list)
    used_global_variables: List[Dict] = field(default_factory=list)
    used_macros: List[Dict] = field(default_factory=list)
    used_structs: List[Dict] = field(default_factory=list)
    
    # 호출 관계
    called_functions: List[str] = field(default_factory=list)
    called_by: List[str] = field(default_factory=list)
    
    # 생성된 아티팩트 (옵션)
    mybatis_xml: Optional[str] = None
    omm_code: Optional[str] = None
    dbio_code: Optional[str] = None
    dao_code: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """딕셔너리로 변환"""
        result = {
            "name": self.name,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "return_type": self.return_type,
            "parameters": self.parameters,
            "sql": self.sql,
            "local_variables": self.local_variables,
            "used_global_variables": self.used_global_variables,
            "used_macros": self.used_macros,
            "used_structs": self.used_structs,
            "called_functions": self.called_functions,
            "called_by": self.called_by,
        }
        
        # 옵션 아티팩트는 값이 있을 때만 포함
        if self.mybatis_xml:
            result["mybatis_xml"] = self.mybatis_xml
        if self.omm_code:
            result["omm_code"] = self.omm_code
        if self.dbio_code:
            result["dbio_code"] = self.dbio_code
        if self.dao_code:
            result["dao_code"] = self.dao_code
            
        return result
    
    def to_json(self, indent: int = 2) -> str:
        """JSON 문자열로 변환"""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "FunctionContext":
        """딕셔너리에서 생성"""
        return cls(
            name=data.get("name", ""),
            line_start=data.get("line_start", 0),
            line_end=data.get("line_end", 0),
            return_type=data.get("return_type", "void"),
            parameters=data.get("parameters", []),
            raw_content=data.get("raw_content", ""),
            sql=data.get("sql", []),
            local_variables=data.get("local_variables", []),
            used_global_variables=data.get("used_global_variables", []),
            used_macros=data.get("used_macros", []),
            used_structs=data.get("used_structs", []),
            called_functions=data.get("called_functions", []),
            called_by=data.get("called_by", []),
            mybatis_xml=data.get("mybatis_xml"),
            omm_code=data.get("omm_code"),
            dbio_code=data.get("dbio_code"),
            dao_code=data.get("dao_code"),
        )
    
    def summary(self) -> str:
        """간단한 요약 문자열 반환"""
        return (
            f"Function '{self.name}' ({self.line_start}-{self.line_end}): "
            f"SQL={len(self.sql)}, LocalVars={len(self.local_variables)}, "
            f"GlobalVars={len(self.used_global_variables)}, "
            f"Macros={len(self.used_macros)}, Structs={len(self.used_structs)}"
        )


@dataclass
class FunctionInfo:
    """함수 인덱싱을 위한 간단한 정보"""
    name: str
    line_start: int
    line_end: int
    return_type: str = "void"
    parameters: List[str] = field(default_factory=list)
