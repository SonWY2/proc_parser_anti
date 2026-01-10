# Pro*C → Java/MyBatis 변환 워크플로우

Pro*C 프로그램을 분석하여 Java/MyBatis 기반의 DAO, DTO, DBIO 파일을 생성하는 전체 프로세스입니다.

---

## 전체 흐름도 (ASCII)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              입력 파일들                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌──────────────┐         ┌──────────────┐         ┌──────────────┐       │
│   │  program.pc  │         │  program.h   │         │ macros.json  │       │
│   │  (Pro*C 코드) │         │ (헤더 파일)   │         │ (매크로 정의) │       │
│   └──────┬───────┘         └──────┬───────┘         └──────┬───────┘       │
│          │                        │                        │               │
└──────────┼────────────────────────┼────────────────────────┼───────────────┘
           │                        │                        │
           ▼                        ▼                        │
┌──────────────────┐     ┌──────────────────┐                │
│   ProCParser     │     │   HeaderParser   │◄───────────────┘
│                  │     │                  │
│ • SQL 추출       │     │ • typedef 파싱   │
│ • 함수 분석      │     │ • STP 배열 파싱  │
│ • 변수 추출      │     │ • 주석 추출      │
└────────┬─────────┘     └────────┬─────────┘
         │                        │
         ▼                        ▼
┌──────────────────┐     ┌──────────────────┐
│  sql_calls.yaml  │     │  db_vars_info    │
│                  │     │                  │
│ • name           │     │ • struct_name    │
│ • sql_type       │     │ • field_name     │
│ • parsed_sql     │     │ • dtype/size     │
│ • input_vars     │     │ • description    │
│ • output_vars    │     │ • arrayReference │
└────────┬─────────┘     └────────┬─────────┘
         │                        │
         │    ┌───────────────────┘
         │    │
         ▼    ▼
┌──────────────────────────────────────────┐
│              OMM Generator               │
│                                          │
│  db_vars_info → .omm 파일 생성            │
│  • SVC DTO (입출력 구조체)                 │
│  • DAO DTO (SQL 변수)                     │
└────────────────────┬─────────────────────┘
                     │
                     ▼
         ┌──────────────────────┐
         │   id_to_path_map     │
         │                      │
         │ SQL ID → DTO 경로    │
         └──────────┬───────────┘
                    │
         ┌──────────┴──────────┐
         │                     │
         ▼                     ▼
┌──────────────────┐   ┌──────────────────┐
│  DBIO Generator  │   │  DAO Generator   │
│                  │   │   (미구현)        │
│  → .dbio 파일    │   │  → .java 파일    │
│  (MyBatis XML)   │   │  (DAO 인터페이스) │
└────────┬─────────┘   └────────┬─────────┘
         │                      │
         ▼                      ▼
┌─────────────────────────────────────────┐
│              출력 디렉토리               │
├─────────────────────────────────────────┤
│                                         │
│  output/                                │
│  ├── omm/                               │
│  │   ├── svc/                           │
│  │   │   ├── ProgramIn.omm              │
│  │   │   └── ProgramOut.omm             │
│  │   └── dao/                           │
│  │       ├── SelectUserIn.omm           │
│  │       └── SelectUserOut.omm          │
│  ├── dbio/                              │
│  │   └── ProgramDao.dbio                │
│  └── dao/                               │
│      └── ProgramDao.java                │
│                                         │
└─────────────────────────────────────────┘
```

---

## 단계별 프로세스

### Phase 1: Pro*C 파일 파싱

```
┌────────────┐      ┌──────────────┐      ┌─────────────────┐
│ program.pc │ ───▶ │  ProCParser  │ ───▶ │ elements[]      │
└────────────┘      └──────────────┘      │ • sql           │
                                          │ • function      │
                                          │ • variable      │
                                          │ • struct        │
                                          └─────────────────┘
```

**입력**: `.pc` 파일
**처리**: `ProCParser.parse_file()`
**출력**: 요소 리스트 (SQL, 함수, 변수, 구조체 등)

---

### Phase 2: 헤더 파일 파싱

```
┌────────────┐      ┌────────────────────────────┐
│ program.h  │ ───▶ │       HeaderParser         │
└────────────┘      ├────────────────────────────┤
      │             │ 1. TypedefStructParser     │
      │             │    └─ typedef struct 파싱   │
      │             │                            │
      │             │ 2. STPParser               │
      │             │    └─ _stp[] 배열 파싱      │
      │             │    └─ size/decimal 업데이트 │
      │             │                            │
      └─ macros ──▶ │ 3. 매크로 치환              │
                    │    └─ MAX_SIZE → 30        │
                    └─────────────┬──────────────┘
                                  │
                                  ▼
                    ┌─────────────────────────────┐
                    │       db_vars_info          │
                    │                             │
                    │ {                           │
                    │   "struct_name_t": {        │
                    │     "fieldName": {          │
                    │       "dtype": "String",    │
                    │       "size": 8,            │
                    │       "description": "..."  │
                    │     }                       │
                    │   }                         │
                    │ }                           │
                    └─────────────────────────────┘
```

---

### Phase 3: OMM 파일 생성

```
┌───────────────┐      ┌─────────────────┐      ┌──────────────────────┐
│ db_vars_info  │ ───▶ │  OMMGenerator   │ ───▶ │ StructName.omm       │
└───────────────┘      └─────────────────┘      │                      │
                                                │ OMM package.Class    │
                                                │ < logicalName=...>   │
                                                │ {                    │
                                                │   String field<...>; │
                                                │ }                    │
                                                └──────────────────────┘
```

---

### Phase 4: DBIO 파일 생성

```
┌───────────────┐
│  sql_calls    │───┐
└───────────────┘   │      ┌─────────────────┐      ┌──────────────────┐
                    ├────▶ │  DBIOGenerator  │ ───▶ │ ProgramDao.dbio  │
┌───────────────┐   │      └─────────────────┘      │                  │
│ id_to_path_map│───┘                               │ <?xml ...?>      │
└───────────────┘                                   │ <mapper ...>     │
                                                    │   <select ...>   │
                                                    │ </mapper>        │
                                                    └──────────────────┘
```

---

## 데이터 흐름 요약

| 단계 | 입력 | 모듈 | 출력 |
|------|------|------|------|
| 1 | `.pc` 파일 | `ProCParser` | SQL/함수/변수 목록 |
| 2 | `.h` 파일 + 매크로 | `HeaderParser` | `db_vars_info` |
| 3 | `db_vars_info` | `OMMGenerator` | `.omm` 파일 |
| 4 | SQL + DTO 매핑 | `DBIOGenerator` | `.dbio` 파일 |

---

## 사용 예시

```python
from header_parser import HeaderParser
from omm_generator import OMMGenerator
from dbio_generator import DBIOGenerator
from proc_parser import ProCParser

# 1. Pro*C 파싱
pc_parser = ProCParser()
elements = pc_parser.parse_file("program.pc")
sql_calls = [el for el in elements if el['type'] == 'sql']

# 2. 헤더 파싱
header_parser = HeaderParser(external_macros={"MAX_SIZE": 30})
db_vars_info = header_parser.parse_file("program.h")

# 3. OMM 생성
omm_gen = OMMGenerator(base_package="com.example.dto", output_dir="./output/omm")
omm_gen.write_all(db_vars_info)

# 4. DBIO 생성
dbio_gen = DBIOGenerator(base_package="com.example.dao", output_dir="./output/dbio")
dbio_content = dbio_gen.generate(sql_calls, id_to_path_map, "ProgramDao")
dbio_gen.write(dbio_content, "ProgramDao")
```

---

## 타입 변환 규칙

```
┌──────────────────────────────────────────────────────────────┐
│                    shared_config 모듈                        │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  C 타입          Java 타입        JDBC 타입                  │
│  ─────────────────────────────────────────                   │
│  int       →     Integer     →    INTEGER                    │
│  char      →     String      →    VARCHAR                    │
│  long      →     BigDecimal  →    NUMERIC                    │
│  double    →     BigDecimal  →    DECIMAL                    │
│                                                              │
│  SQL 타입        MyBatis 태그                                 │
│  ─────────────────────────────                               │
│  SELECT    →     <select>                                    │
│  INSERT    →     <insert>                                    │
│  UPDATE    →     <update>                                    │
│  DELETE    →     <delete>                                    │
│  CREATE    →     <update>  (DDL)                             │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```
