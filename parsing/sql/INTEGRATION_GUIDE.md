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

---

## 8. 새로운 SQL 패턴 추가 가이드

### 8.1 새로운 SQL 타입 규칙 추가

새로운 SQL 구문(예: `EXEC SQL MERGE`, `EXEC SQL LOCK TABLE`)을 인식하려면:

#### 방법 1: 인라인 등록 (간단한 경우)

```python
import re
from sql_extractor import SQLTypeRule

class LockTableRule(SQLTypeRule):
    """LOCK TABLE 규칙"""
    
    @property
    def name(self):
        return "lock_table"
    
    @property
    def priority(self):
        return 60  # 우선순위 (높을수록 먼저 검사)
    
    @property
    def pattern(self):
        return re.compile(r'EXEC\s+SQL\s+LOCK\s+TABLE', re.IGNORECASE)

# 등록
extractor.sql_type_registry.register(LockTableRule())
```

#### 방법 2: 별도 파일로 관리 (권장)

1. `sql_extractor/rules/custom_rules.py` 생성:

```python
# sql_extractor/rules/custom_rules.py
import re
from .base import SQLTypeRule, RuleMatch

class LockTableRule(SQLTypeRule):
    @property
    def name(self):
        return "lock_table"
    
    @property
    def priority(self):
        return 60
    
    @property
    def pattern(self):
        return re.compile(r'EXEC\s+SQL\s+LOCK\s+TABLE', re.IGNORECASE)

class SavepointRule(SQLTypeRule):
    @property
    def name(self):
        return "savepoint"
    
    @property
    def priority(self):
        return 60
    
    @property
    def pattern(self):
        return re.compile(r'EXEC\s+SQL\s+SAVEPOINT', re.IGNORECASE)

# 모든 커스텀 규칙 리스트
CUSTOM_RULES = [
    LockTableRule(),
    SavepointRule(),
]
```

2. 사용:

```python
from sql_extractor.rules.custom_rules import CUSTOM_RULES

extractor = SQLExtractor()
extractor.sql_type_registry.register_many(CUSTOM_RULES)
```

---

### 8.2 복잡한 매칭 로직 (match 메서드 오버라이드)

단순 정규식으로 불충분한 경우 `match()` 메서드를 오버라이드:

```python
class CallProcedureRule(SQLTypeRule):
    """CALL procedure_name 규칙 - 프로시저명 추출"""
    
    @property
    def name(self):
        return "call_procedure"
    
    @property
    def priority(self):
        return 65
    
    @property
    def pattern(self):
        return re.compile(r'EXEC\s+SQL\s+CALL\s+(\w+)', re.IGNORECASE)
    
    def match(self, sql_text):
        m = self.pattern.search(sql_text)
        if m:
            procedure_name = m.group(1)
            return RuleMatch(
                matched=True,
                value=self.name,
                metadata={
                    'procedure_name': procedure_name,
                    'call_type': 'stored_procedure'
                }
            )
        return RuleMatch(matched=False)
```

---

### 8.3 새로운 호스트 변수 패턴 추가

비표준 호스트 변수 형식(예: `@variable`, `#temp`)을 인식하려면:

```python
import re
from sql_extractor.rules.base import HostVariableRule

class AtSignVariableRule(HostVariableRule):
    """@variable 패턴 (SQL Server 스타일)"""
    
    @property
    def name(self):
        return "at_sign"
    
    @property
    def pattern(self):
        return re.compile(r'@(\w+)')
    
    def extract(self, match):
        return {
            'type': self.name,
            'var_name': match.group(1),
            'style': 'sqlserver'
        }

# 등록
extractor.host_var_registry.register(AtSignVariableRule())
```

---

### 8.4 DBMS별 규칙 파일 구성

Oracle, DB2, SQL Server 등 DBMS별로 규칙을 분리:

```
sql_extractor/rules/
├── base.py              # 기본 클래스
├── sql_type_rules.py    # 공통 SQL 타입
├── host_variable_rules.py  # 공통 호스트 변수
├── db2_rules.py         # DB2 전용 (기존)
├── oracle_rules.py      # Oracle 전용 (새로 생성)
└── sqlserver_rules.py   # SQL Server 전용 (새로 생성)
```

**Oracle 규칙 예시 (`oracle_rules.py`):**

```python
import re
from .base import SQLTypeRule, RuleMatch

class SelectForUpdateRule(SQLTypeRule):
    """SELECT ... FOR UPDATE (Oracle)"""
    
    @property
    def name(self):
        return "select"
    
    @property
    def priority(self):
        return 55
    
    @property
    def pattern(self):
        return re.compile(
            r'EXEC\s+SQL\s+SELECT[\s\S]*?FOR\s+UPDATE',
            re.IGNORECASE
        )
    
    def match(self, sql_text):
        if self.pattern.search(sql_text):
            return RuleMatch(
                matched=True,
                value=self.name,
                metadata={'lock_mode': 'FOR_UPDATE', 'dbms': 'oracle'}
            )
        return RuleMatch(matched=False)

class PlusJoinRule(SQLTypeRule):
    """Oracle (+) 조인 구문"""
    
    @property
    def name(self):
        return "select"
    
    @property
    def priority(self):
        return 51
    
    @property
    def pattern(self):
        return re.compile(
            r'EXEC\s+SQL\s+SELECT[\s\S]*?\(\+\)',
            re.IGNORECASE
        )
    
    def match(self, sql_text):
        if self.pattern.search(sql_text):
            return RuleMatch(
                matched=True,
                value=self.name,
                metadata={'join_style': 'oracle_plus', 'dbms': 'oracle'}
            )
        return RuleMatch(matched=False)

ORACLE_RULES = [
    SelectForUpdateRule(),
    PlusJoinRule(),
]
```

**Registry에 로드 메서드 추가:**

```python
# registry.py에 추가
def load_oracle_rules(self):
    from .rules.oracle_rules import ORACLE_RULES
    self.register_many(ORACLE_RULES)
```

---

### 8.5 우선순위 가이드

규칙 우선순위 설정 권장값:

| 범위 | 용도 | 예시 |
|------|------|------|
| 100 | 최우선 (전처리) | INCLUDE, BEGIN/END DECLARE |
| 90 | 커서 선언 | DECLARE CURSOR |
| 80 | 커서 작업 | OPEN, CLOSE, FETCH |
| 70 | 동적 SQL | PREPARE, EXECUTE |
| 65 | 연결 관련 | CONNECT, DISCONNECT |
| 60 | 트랜잭션 | COMMIT, ROLLBACK, SAVEPOINT |
| 55 | DBMS 특수 구문 | WITH UR, FOR UPDATE |
| 50 | 기본 DML | SELECT, INSERT, UPDATE, DELETE |
| 40 | 기타 | 분류되지 않은 구문 |

**중요:** 우선순위가 같으면 먼저 등록된 규칙이 적용됩니다.

---

### 8.6 테스트 추가

새 규칙을 추가했다면 테스트도 추가하세요:

```python
# tests/test_custom_rules.py

def test_lock_table_rule():
    from sql_extractor import SQLExtractor
    from your_custom_rules import LockTableRule
    
    extractor = SQLExtractor()
    extractor.sql_type_registry.register(LockTableRule())
    
    result = extractor.sql_type_registry.determine_type(
        "EXEC SQL LOCK TABLE users IN EXCLUSIVE MODE;"
    )
    
    assert result.matched
    assert result.value == "lock_table"

def test_call_procedure_metadata():
    from sql_extractor import SQLExtractor
    from your_custom_rules import CallProcedureRule
    
    extractor = SQLExtractor()
    extractor.sql_type_registry.register(CallProcedureRule())
    
    result = extractor.sql_type_registry.determine_type(
        "EXEC SQL CALL process_order(:order_id);"
    )
    
    assert result.value == "call_procedure"
    assert result.metadata['procedure_name'] == 'process_order'
```

