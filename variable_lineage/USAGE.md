# Variable Lineage Tracker 사용 가이드

Pro*C 코드에서 추출된 변수들이 MyBatis/Java로 변환되는 과정에서의 연결관계(Lineage)를 추적합니다.

## 기본 사용법

```python
from variable_lineage import VariableLineageTracker

# 트래커 생성
tracker = VariableLineageTracker(source_file="sample.pc")

# 1. proc_parser 결과 추가
elements = parser.parse_file("sample.pc")
tracker.add_from_proc_parser(elements)

# 2. header_parser 결과 추가
db_vars_info = header_parser.parse_file("sample.h")
tracker.add_from_header_parser(db_vars_info)

# 3. 연결관계 자동 구축
tracker.build_links()

# 4. JSON 출력
print(tracker.to_json())
```

## 추적되는 변환 규칙

| 변환 | 예시 | 기록 |
|------|------|------|
| Prefix `H_o_` 제거 | `H_o_result` → `result` | `prefix_removed:H_o_` |
| Prefix `H_i_` 제거 | `H_i_input` → `input` | `prefix_removed:H_i_` |
| Prefix `H_` 제거 | `H_user` → `user` | `prefix_removed:H_` |
| Prefix `W_` 제거 | `W_buffer` → `buffer` | `prefix_removed:W_` |
| snake → camelCase | `user_id` → `userId` | `snake_to_camel` |

## JSON 출력 형식

```json
{
  "source_file": "sample.pc",
  "nodes": {
    "proc_var_H_o_user_id": {
      "id": "proc_var_H_o_user_id",
      "name": "H_o_user_id",
      "node_type": "proc_variable",
      "source_module": "proc_parser",
      "metadata": {"data_type": "char", "size": 9}
    }
  },
  "links": [
    {
      "source_id": "proc_var_H_o_user_id",
      "target_id": "sql_host_out_sql_001_user_id",
      "link_type": "used_in",
      "confidence": 0.9,
      "transformations": ["prefix_removed:H_o_"]
    }
  ],
  "summary": {
    "total_nodes": 5,
    "total_links": 3,
    "nodes_by_type": {"proc_variable": 2, "sql_host_var": 3}
  }
}
```

## 변수 추적 쿼리

```python
# 특정 변수의 upstream/downstream 추적
result = tracker.query_lineage("user_id")
print(result['upstream'])    # 상위 노드들
print(result['downstream'])  # 하위 노드들
```

## 커스텀 Prefix 설정

```python
from variable_lineage.tracker import LineageConfig

config = LineageConfig(
    prefixes=['H_o_', 'H_i_', 'H_', 'W_', 'CUSTOM_'],
    case_insensitive=True
)
tracker = VariableLineageTracker(config=config)
```

## 노드 타입

| 타입 | 설명 | 소스 모듈 |
|------|------|----------|
| `proc_variable` | Pro*C 변수 선언 | proc_parser |
| `struct_field` | 구조체 필드 | header_parser |
| `sql_host_var` | SQL 호스트 변수 | proc_parser, sql_extractor |
| `omm_field` | OMM 파일 필드 | omm_generator |
| `mybatis_param` | MyBatis 파라미터 | dbio_generator |
| `java_variable` | Java 변수 (camelCase) | variable_lineage |

## 연결 타입

| 타입 | 설명 |
|------|------|
| `declared_as` | 변수 → 호스트변수 선언 |
| `used_in` | SQL에서 사용됨 |
| `transformed_to` | 네이밍 변환됨 |
| `mapped_to` | OMM/MyBatis 매핑 |

---

## Neo4j Export

Lineage 그래프를 Neo4j로 내보냅니다.

### Cypher 파일 생성

```python
from variable_lineage import VariableLineageTracker, Neo4jExporter

# 트래커 생성 및 데이터 추가
tracker = VariableLineageTracker(source_file="sample.pc")
tracker.add_from_proc_parser(elements)
tracker.add_java_variables()  # JavaVariable 노드 자동 생성
tracker.build_links()

# Neo4j Exporter
exporter = Neo4jExporter(program_name="my_program")
exporter.save_cypher(tracker.graph, "output.cypher")
```

### Neo4j Driver 직접 연결

```python
from neo4j import GraphDatabase

driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "password"))
result = exporter.export_to_driver(tracker.graph, driver)
print(f"노드: {result['nodes_created']}, 관계: {result['relationships_created']}")
```

### 스키마 매핑

| Tracker 노드 | Neo4j Label |
|-------------|-------------|
| proc_variable | ProCVariable |
| struct_field | FieldDefinition |
| sql_host_var | SQLHostVariable |
| java_variable | JavaVariable |
| omm_field | OMMField |
