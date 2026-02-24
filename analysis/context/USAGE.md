# Function Context 모듈 사용 가이드

특정 함수에 대한 모든 관련 정보(SQL, 변수, 매크로, 구조체, 아티팩트)를 추출합니다.

## 빠른 시작

```python
from proc_parser.unified_metadata_generator import UnifiedMetadataGenerator
from function_context import FunctionContextExtractor

# 1. 메타데이터 생성
generator = UnifiedMetadataGenerator()
metadata = generator.generate("sample.pc")

# 2. 추출기 생성
extractor = FunctionContextExtractor(metadata)

# 3. 함수 목록 확인
print(extractor.list_functions())
# ['main', 'process_data', 'save_result']

# 4. 특정 함수 컨텍스트 추출
ctx = extractor.extract("process_data")
print(ctx.summary())
# Function 'process_data' (10-50): SQL=3, LocalVars=5, GlobalVars=2, Macros=1, Structs=0
```

---

## 주요 API

### FunctionContextExtractor

| 메서드 | 설명 |
|--------|------|
| `list_functions()` | 모든 함수명 목록 반환 |
| `extract(name, **options)` | 특정 함수 컨텍스트 추출 |
| `extract_all(**options)` | 모든 함수 컨텍스트 추출 |
| `get_function_summary(name)` | 함수 요약 문자열 반환 |
| `export_function_json(name, path)` | 함수 컨텍스트를 JSON으로 저장 |
| `export_all_json(path)` | 모든 함수 컨텍스트를 JSON으로 저장 |

### extract() 옵션

```python
ctx = extractor.extract(
    "process_data",
    include_sql=True,           # SQL 포함 (기본: True)
    include_variables=True,     # 변수 포함 (기본: True)
    include_macros=True,        # 매크로 포함 (기본: True)
    include_structs=True,       # 구조체 포함 (기본: True)
    include_mybatis=False,      # MyBatis XML 생성 (기본: False)
    include_omm=False,          # OMM VO 생성 (기본: False)
    include_dbio=False,         # DBIO 클래스 생성 (기본: False)
    include_dao=False,          # DAO 인터페이스 생성 (기본: False)
)
```

---

## FunctionContext 객체

```python
@dataclass
class FunctionContext:
    name: str                      # 함수명
    line_start: int                # 시작 라인
    line_end: int                  # 종료 라인
    return_type: str               # 반환 타입
    parameters: List[str]          # 매개변수 목록
    
    # 추출된 요소들
    sql: List[Dict]                # SQL 목록
    local_variables: List[Dict]    # 로컬 변수
    used_global_variables: List[Dict]  # 사용된 전역 변수
    used_macros: List[Dict]        # 사용된 매크로
    used_structs: List[Dict]       # 사용된 구조체
    
    # 아티팩트 (옵션)
    mybatis_xml: Optional[str]     # MyBatis XML
    omm_code: Optional[str]        # OMM VO 클래스
    dbio_code: Optional[str]       # DBIO 클래스
    dao_code: Optional[str]        # DAO 인터페이스
```

---

## 예제

### 1. 함수별 SQL 분석

```python
extractor = FunctionContextExtractor(metadata)

for func_name in extractor.list_functions():
    ctx = extractor.extract(func_name, include_sql=True)
    print(f"{func_name}: {len(ctx.sql)}개 SQL")
    for sql in ctx.sql:
        print(f"  - {sql.get('sql_id')}: {sql.get('sql_type')}")
```

### 2. MyBatis XML 생성

```python
ctx = extractor.extract(
    "process_data",
    include_sql=True,
    include_mybatis=True
)

print(ctx.mybatis_xml)
# <?xml version="1.0" encoding="UTF-8"?>
# <mapper namespace="com.example.mapper.process_data">
#   <select id="select_0" resultType="map">
#     SELECT * FROM users WHERE id = #{id}
#   </select>
# </mapper>
```

### 3. OMM/DBIO/DAO 생성

```python
ctx = extractor.extract(
    "process_data",
    include_variables=True,
    include_sql=True,
    include_omm=True,
    include_dbio=True,
    include_dao=True
)

# OMM VO 클래스
print(ctx.omm_code)

# DBIO 클래스
print(ctx.dbio_code)

# DAO 인터페이스
print(ctx.dao_code)
```

### 4. JSON 내보내기

```python
# 특정 함수
extractor.export_function_json(
    "process_data",
    "process_data_context.json",
    include_sql=True,
    include_mybatis=True
)

# 모든 함수
extractor.export_all_json(
    "all_functions_context.json",
    include_sql=True,
    include_variables=True
)
```

---

## 의존성

- Python 3.7+
- proc_parser.unified_metadata_generator (메타데이터 생성)
- omm_generator (옵션, OMM 생성 시)
- dbio_generator (옵션, DBIO 생성 시)
- dao_generator (옵션, DAO 생성 시)
