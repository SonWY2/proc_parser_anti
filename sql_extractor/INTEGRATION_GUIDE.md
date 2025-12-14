# SQL Extractor 통합 가이드

새로운 `sql_extractor` 패키지를 기존 코드와 통합하는 방법을 안내합니다.

---

## 1. 기본 설치

`sql_extractor` 패키지는 `proc_parser/sql_extractor/` 디렉토리에 위치합니다.

```
proc_parser/
├── sql_extractor/           # 새로운 패키지
│   ├── __init__.py
│   ├── extractor.py         # SQLExtractor 클래스
│   ├── config.py            # 설정
│   ├── registry.py          # 규칙 레지스트리
│   ├── tree_sitter_extractor.py
│   └── rules/               # 규칙 모듈
└── parser_core.py           # 기존 코드
```

---

## 2. 기존 코드와 통합

### 2.1 Import 변경

```python
# 기존
# from your_module import SQLExtractor

# 변경
from sql_extractor import SQLExtractor, SQLExtractorConfig
```

### 2.2 초기화 (기존과 동일)

```python
# 기존 file_manager, code_analyzer 그대로 사용
extractor = SQLExtractor(
    file_manager=your_file_manager,
    code_analyzer=your_code_analyzer,
    config=SQLExtractorConfig()
)
```

### 2.3 메서드 호출 (기존과 동일)

```python
# DECLARE SECTION 분해
code = extractor.decompose_declare_section(code, file_key, program_dict)

# SQL 분해
code = extractor.decompose_sql(code, file_key, program_dict, variables)

# SQL 주석 버전 생성
commented = extractor.create_sql_commented_version(code, file_key)

# SQL-함수 매핑
mapping = extractor.map_sql_to_functions(file_key, funcs)
```

---

## 3. parser_core.py 통합 예시

기존 `parser_core.py`의 SQL 추출 로직을 새 패키지로 교체하려면:

```python
# parser_core.py

from sql_extractor import SQLExtractor, SQLExtractorConfig

class ProCParser:
    def __init__(self):
        self.c_parser = CParser()
        self.sql_converter = SQLConverter()
        
        # 새로운 SQL 추출기 초기화
        self.sql_extractor = SQLExtractor(
            config=SQLExtractorConfig()
        )
        
        # DB2 프로젝트인 경우 규칙 추가
        # self.sql_extractor.sql_type_registry.load_db2_rules()
    
    def parse_file(self, file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 기존 정규식 대신 새로운 추출기 사용
        functions = self.sql_extractor.tree_sitter_extractor.get_functions(content)
        sql_blocks = self.sql_extractor.tree_sitter_extractor.extract_sql_blocks(
            content, functions
        )
        
        elements = []
        for block in sql_blocks:
            # 타입 결정
            result = self.sql_extractor.sql_type_registry.determine_type(block.text)
            
            # 호스트 변수 추출
            host_vars = self.sql_extractor.host_var_registry.extract_all(block.text)
            
            elements.append({
                "type": "sql",
                "raw_content": block.text,
                "sql_type": result.value,
                "line_start": block.start_line,
                "line_end": block.end_line,
                "function": block.containing_function,
                "host_variables": host_vars,
                "metadata": result.metadata,
            })
        
        return elements
```

---

## 4. DB2 프로젝트 지원

DB2 구문(WITH UR, FETCH FIRST 등)을 인식하려면:

```python
extractor = SQLExtractor()
extractor.sql_type_registry.load_db2_rules()

# 이제 WITH UR 등 메타데이터 포함
result = extractor.sql_type_registry.determine_type(
    "EXEC SQL SELECT * FROM t WITH UR;"
)
print(result.metadata)  # {'isolation_level': 'UR', 'dbms': 'db2'}
```

---

## 5. 커스텀 규칙 추가

새로운 SQL 타입이나 호스트 변수 패턴을 추가하려면:

```python
import re
from sql_extractor import SQLTypeRule

class MergeRule(SQLTypeRule):
    @property
    def name(self):
        return "merge"
    
    @property
    def priority(self):
        return 55  # SELECT(50)보다 높게
    
    @property
    def pattern(self):
        return re.compile(r'EXEC\s+SQL\s+MERGE', re.IGNORECASE)

# 등록
extractor.sql_type_registry.register(MergeRule())
```

---

## 6. 의존성

### 필수
- Python 3.8+

### 선택 (성능 향상)
```bash
pip install tree-sitter tree-sitter-c
```

tree-sitter가 없으면 자동으로 정규식 fallback을 사용합니다.

---

## 7. API 참조

### SQLExtractor

| 메서드 | 설명 |
|--------|------|
| `decompose_declare_section(code, file_key, program_dict)` | DECLARE SECTION 분해 |
| `decompose_sql(code, file_key, program_dict, variables)` | SQL 분해 |
| `create_sql_commented_version(code, file_key)` | SQL 주석 버전 |
| `map_sql_to_functions(file_key, funcs)` | SQL-함수 매핑 |

### SQLTypeRegistry

| 메서드 | 설명 |
|--------|------|
| `load_defaults()` | 기본 규칙 로드 |
| `load_db2_rules()` | DB2 규칙 로드 |
| `register(rule)` | 커스텀 규칙 등록 |
| `determine_type(sql_text)` | SQL 타입 결정 |

### HostVariableRegistry

| 메서드 | 설명 |
|--------|------|
| `load_defaults()` | 기본 규칙 로드 |
| `extract_all(sql_text)` | 호스트 변수 추출 |
| `classify_by_direction(sql_text, sql_type)` | 입력/출력 분류 |
