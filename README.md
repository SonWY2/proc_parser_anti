# Pro*C Parser

Pro*C 파일(.pc, .h)을 파싱하여 코드 요소별로 분해하고 JSONL 형식으로 출력하는 파서입니다.

## 주요 기능

- **코드 요소 추출**: Include, 변수, 함수, 구조체, 매크로, 주석 등을 분리하여 추출
- **SQL 변환**: Pro*C 임베디드 SQL을 표준 SQL 형식으로 변환
- **호스트 변수 처리**: SQL 문의 input/output 호스트 변수를 자동으로 식별 및 분류
- **SQL 관계 분석**: Cursor, Dynamic SQL, Transaction, Array DML 패턴을 감지하고 그룹화
- **플러그인 시스템**: BAMCALL() 등의 커스텀 구조를 플러그인으로 확장 가능
- **미분류 요소 탐지**: 파싱되지 않은 코드 영역을 자동으로 감지하여 보고

## 설치

```bash
pip install tree-sitter
```

## 사용법

```bash
python main.py <입력_디렉토리> <출력_디렉토리>
```

### 예시

```bash
python main.py ./proc_files ./outputs
```

## 출력 형식

각 코드 요소는 별도의 JSONL 파일로 저장됩니다:

- `function.jsonl`: 함수 선언 및 정의
- `variable.jsonl`: 변수 선언
- `struct.jsonl`: 구조체 정의
- `macro.jsonl`: 매크로 정의
- `sql.jsonl`: SQL 문 (표준화된 형식 + 관계 정보)
- `comment.jsonl`: 주석
- `include.jsonl`: Include 문
- `bam_call.jsonl`: BAMCALL() 등 플러그인이 처리한 특수 구조
- `unknown.jsonl`: 파싱되지 않은 코드 조각

### SQL 관계 정보 (MyBatis 변환용)

SQL 문에는 `relationship` 필드가 포함되어 다음 패턴을 지원합니다:

#### 1. Cursor 패턴
```json
{
  "sql_id": "sql_001",
  "sql_type": "DECLARE",
  "relationship": {
    "relationship_type": "CURSOR",
    "metadata": {
      "cursor_name": "emp_cursor",
      "cursor_query": "SELECT id, name FROM employees",
      "is_loop_based": true,
      "all_output_vars": [":emp_id", ":emp_name"]
    }
  }
}
```

**MyBatis 변환 활용:**
- `cursor_query` → `<select>` 쿼리
- `all_output_vars` → `<resultMap>` 매핑
- `is_loop_based` → `List<T>` vs 단일 객체 결정

#### 2. Dynamic SQL 패턴
```json
{
  "relationship_type": "DYNAMIC_SQL",
  "metadata": {
    "statement_name": "stmt1",
    "is_literal_source": false,
    "all_parameters": [":param1", ":param2"]
  }
}
```

**MyBatis 변환 활용:**
- 파라미터 → `parameterType` 및 `#{}` 매핑

#### 3. Transaction 패턴
```json
{
  "relationship_type": "TRANSACTION",
  "metadata": {
    "transaction_scope": "function",
    "commit_type": "explicit",
    "has_rollback": false
  }
}
```

**Spring/MyBatis 변환 활용:**
- `@Transactional` 어노테이션 배치
- 트랜잭션 경계 결정

#### 4. Array DML 패턴
```json
{
  "relationship_type": "ARRAY_DML",
  "metadata": {
    "array_size_var": ":batch_size",
    "array_host_vars": [{
      "var": ":ids",
      "is_array": true
    }],
    "dml_type": "INSERT",
    "mybatis_hint": "use_foreach"
  }
}
```

**MyBatis 변환 활용:**
- `<foreach>` 태그로 변환
- Batch insert/update 최적화

## 프로젝트 구조

```
proc_parser/
├── main.py                      # 진입점
├── parser_core.py               # 핵심 파싱 로직
├── c_parser.py                  # tree-sitter 기반 C 파서
├── sql_converter.py             # Pro*C SQL 변환기
├── sql_relationship_plugin.py   # SQL 관계 플러그인 인터페이스
├── file_handler.py              # 파일 I/O 처리
├── plugin_interface.py          # 코드 플러그인 인터페이스
├── patterns.py                  # 정규식 패턴 정의
└── plugins/
    ├── bam_call.py              # BAMCALL() 플러그인
    ├── cursor_relationship.py   # Cursor 관계 플러그인
    ├── dynamic_sql_relationship.py  # Dynamic SQL 관계 플러그인
    ├── transaction_relationship.py  # Transaction 관계 플러그인
    └── array_dml_relationship.py    # Array DML 관계 플러그인
```

## 플러그인 추가

### 코드 플러그인
새로운 특수 구조를 파싱하려면 `PluginInterface`를 구현:

```python
from plugin_interface import PluginInterface

class CustomPlugin(PluginInterface):
    def can_handle(self, text, start_pos):
        # 처리 가능 여부 판단
        pass
    
    def parse(self, text, start_pos):
        # 파싱 로직
        pass
```

### SQL 관계 플러그인
새로운 SQL 패턴을 감지하려면 `SQLRelationshipPlugin`을 구현:

```python
from sql_relationship_plugin import SQLRelationshipPlugin

class BulkCollectPlugin(SQLRelationshipPlugin):
    def can_handle(self, sql_elements):
        # BULK COLLECT 패턴 감지
        pass
    
    def extract_relationships(self, sql_elements):
        # 관계 정보 추출
        pass
```

## 테스트

```bash
# 관계 플러그인 테스트
python tests/test_sql_relationships.py

# 전체 파서 테스트
python main.py tests outputs_test
```

## 기술 스택

- **tree-sitter**: C 코드 구문 분석
- **Python 3.x**: 메인 언어
- **정규식**: SQL 및 특수 패턴 매칭
- **플러그인 아키텍처**: 확장 가능한 파서 설계
