"""노드 연결 관계 테스트"""
from analysis.lineage import VariableLineageTracker
from analysis.lineage.types import NodeType, LinkType
from parsing.core import ProCParser
from parsing.header import HeaderParser
import os

# 파싱
parser = ProCParser()
elements = parser.parse_file('sample_input/enterprise_complex_sql.pc')

# 헤더 파싱 - 실제 존재하는 파일 사용
header_file = 'sample_input/sample.h'
db_vars_info = {}
if os.path.exists(header_file):
    hp = HeaderParser()
    result = hp.parse_file(header_file)
    # 반환 타입에 따라 처리
    if isinstance(result, dict):
        db_vars_info = result
    elif isinstance(result, tuple) and len(result) >= 1:
        db_vars_info = result[0] if isinstance(result[0], dict) else {}

# 트래커 설정
tracker = VariableLineageTracker(source_file='enterprise_complex_sql.pc')
tracker.add_all_program_elements(elements)
if db_vars_info:
    tracker.add_from_header_parser(db_vars_info)
tracker.add_java_variables()
tracker.build_links()

# 노드 타입별 개수
print('=' * 60)
print('Node Type Summary')
print('=' * 60)
counts = {}
for n in tracker.graph.nodes.values():
    t = n.node_type.value
    counts[t] = counts.get(t, 0) + 1
for t, c in sorted(counts.items()):
    print(f'  {t:20} : {c}')
print(f'\n  Total Nodes: {sum(counts.values())}')

# 링크 타입별 개수
print('\n' + '=' * 60)
print('Link Type Summary')
print('=' * 60)
lcounts = {}
for l in tracker.graph.links:
    t = l.link_type.value
    lcounts[t] = lcounts.get(t, 0) + 1
for t, c in sorted(lcounts.items()):
    print(f'  {t:20} : {c}')
print(f'\n  Total Links: {sum(lcounts.values())}')

# 연결 관계 유형별 정리
print('\n' + '=' * 60)
print('Connection Types (Source --> Target)')
print('=' * 60)
type_pairs = {}
for link in tracker.graph.links:
    src = tracker.graph.get_node(link.source_id)
    tgt = tracker.graph.get_node(link.target_id)
    if src and tgt:
        pair = (src.node_type.value, link.link_type.value, tgt.node_type.value)
        if pair not in type_pairs:
            type_pairs[pair] = []
        type_pairs[pair].append((src.name, tgt.name))

for (src_type, link_type, tgt_type), examples in sorted(type_pairs.items()):
    print(f'\n[{src_type}] --({link_type})--> [{tgt_type}]  ({len(examples)}개)')
    for src_name, tgt_name in examples[:3]:
        print(f'    {src_name} --> {tgt_name}')
    if len(examples) > 3:
        print(f'    ... 외 {len(examples)-3}개 더')

# ASCII 다이어그램
print('\n' + '=' * 60)
print('ASCII Relationship Diagram')
print('=' * 60)
print('''
                     +-------------------+
                     |     PROGRAM       |
                     | (Source File)     |
                     +-------------------+
                              |
         +--------------------+--------------------+
         |                    |                    |
         v                    v                    v
  +-----------+        +-----------+        +-----------+
  | HEADER    |        | FUNCTION  |        |   MACRO   |
  | FILE      |        |           |        |           |
  +-----------+        +-----------+        +-----------+
         |                    |
         v                    +----------------+----------------+
  +-----------+               |                |                |
  | STRUCT    |               v                v                v
  | FIELD     |        +-----------+    +-----------+    +-----------+
  +-----------+        | PROC_VAR  |    |    SQL    |    | BAM_CALL  |
         |             +-----------+    +-----------+    +-----------+
         |                    |                |
         |                    v                v
         |             +-----------+    +-----------+
         +------------>| JAVA_VAR  |    | SQL_HOST  |
                       +-----------+    |   _VAR    |
                              |         +-----------+
                              v                |
                       +-----------+           v
                       | OMM_FIELD |<----------+
                       +-----------+
                              |
                              v
                       +-----------+
                       | MYBATIS   |
                       | PARAM     |
                       +-----------+
''')

# 연결 관계 요약
print('\n' + '=' * 60)
print('Relationship Summary')
print('=' * 60)
print('''
Key Relationships:
  1. PROC_VARIABLE --[TRANSFORMED_TO]--> JAVA_VARIABLE
     (snake_case --> camelCase 변환)
     
  2. STRUCT_FIELD --[MAPPED_TO]--> OMM_FIELD
     (헤더 구조체 --> OMM 파일)
     
  3. SQL_HOST_VAR --[USED_IN]--> MYBATIS_PARAM
     (Pro*C 호스트변수 --> MyBatis 파라미터)
     
  4. FUNCTION --[CONTAINS]--> (SQL, PROC_VARIABLE, BAM_CALL)
     (함수가 포함하는 요소들)
     
  5. PROGRAM --[INCLUDES]--> HEADER_FILE
     (#include 관계)
''')
