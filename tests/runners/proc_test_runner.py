import rich
from proc_parser import ProCParser

parser = ProCParser()
elements = parser.parse_file("sample_input/enterprise_complex_sql.pc")


functions = [el for el in elements if el['type'] == 'function']
print(functions[0].keys())
for function in functions:
    print(function['type'])
    print(function['name'])
    print(function['line_start'])
    print(function['line_end'])
    print(function['raw_content'][:200])
    print("-" * 80)

sqls = [el for el in elements if el['type'] == 'sql']

rich.print(sqls[0].keys())


print(functions[0].keys())
for sql in sqls:
    rich.print(f"{sql['sql_id']=}")
    rich.print(f"{sql['type']=}")
    rich.print(f"{sql['line_start']=}")
    rich.print(f"{sql['line_end']=}")
    rich.print(f"{sql['function']=}")
    rich.print(f"{sql['sql_type']=}")
    rich.print(f"{sql['raw_content'][:200]=}")
    rich.print(f"{sql['normalized_sql']=}")
    rich.print(f"{sql['input_host_vars']=}")
    rich.print(f"{sql['output_host_vars']=}")
    rich.print("-" * 80)


# ============================================================================
# Header Parser 테스트
# ============================================================================
print("\n" + "=" * 80)
print("Header Parser 테스트")
print("=" * 80)

from header_parser import HeaderParser, TypedefStructParser, STPParser

# 1. HeaderParser 통합 테스트
header_parser = HeaderParser(external_macros={"MAX_SIZE": 30})
db_vars_info = header_parser.parse_file("sample_input/sample.h")

print(f"\n파싱된 구조체 수: {len(db_vars_info)}")
for struct_name, fields in db_vars_info.items():
    print(f"\n구조체: {struct_name}")
    print(f"  필드 수: {len(fields)}")
    for field_name, field_info in list(fields.items())[:3]:  # 처음 3개만
        rich.print(f"    {field_name}: {field_info}")
    if len(fields) > 3:
        print(f"    ... 외 {len(fields) - 3}개 필드")

# 2. TypedefStructParser 개별 테스트
typedef_parser = TypedefStructParser()
with open("sample_input/sample.h", "r", encoding="utf-8", errors="ignore") as f:
    content = f.read()

structs = typedef_parser.parse(content)
print(f"\nTypedef 구조체 수: {len(structs)}")
for name, info in list(structs.items())[:2]:
    print(f"  {name}: {len(info.fields)} 필드")

# 3. STPParser 개별 테스트
stp_parser = STPParser()
stp_data = stp_parser.parse(content)
print(f"\nSTP 배열 수: {len(stp_data)}")
for name, items in list(stp_data.items())[:2]:
    print(f"  {name}: {len(items)} 항목")


# ============================================================================
# OMM Generator 테스트
# ============================================================================
print("\n" + "=" * 80)
print("OMM Generator 테스트")
print("=" * 80)

from omm_generator import OMMGenerator

omm_generator = OMMGenerator(
    base_package="sp.spa.frgn.dao.dto",
    output_dir="./debug_output/omm"
)

# 첫 번째 구조체로 OMM 생성
first_struct = list(db_vars_info.keys())[0]
first_vars = db_vars_info[first_struct]

omm_content = omm_generator.generate(first_vars, first_struct)
print(f"\n생성된 OMM ({first_struct}):")
print("-" * 40)
print(omm_content[:500])
if len(omm_content) > 500:
    print("...")

# 파일로 저장
try:
    file_path = omm_generator.write(omm_content, first_struct)
    print(f"\n저장됨: {file_path}")
except Exception as e:
    print(f"\n저장 실패: {e}")


# ============================================================================
# DBIO Generator 테스트
# ============================================================================
print("\n" + "=" * 80)
print("DBIO Generator 테스트")
print("=" * 80)

from dbio_generator import DBIOGenerator

dbio_generator = DBIOGenerator(
    base_package="sp.spa.cbc.dao",
    datasource="MainDS",
    output_dir="./debug_output/dbio"
)

# 테스트용 SQL 데이터
sql_calls = [
    {
        "name": "selectAcntId",
        "sql_type": "select",
        "parsed_sql": "SELECT ACNT_ID as acntId FROM SID.IDO_A_UUA_ACNT WHERE TRIM(ACNT_NO_CRYP) = :acnt_no_cryp",
        "input_vars": ["acntNoCryp"],
        "output_vars": ["acntId"]
    },
    {
        "name": "selectAcntNoCryp",
        "sql_type": "select",
        "parsed_sql": "SELECT ACNT_NO_CRYP as acntNoCryp FROM SID.IDO_A_UUA_ACNT WHERE ACNT_ID = :acnt_id",
        "input_vars": ["acntId"],
        "output_vars": ["acntNoCryp"]
    }
]

id_to_path_map = {
    "selectAcntIdIn": "sp.spa.cbc.dao.dto.SelectAcntIdIn",
    "selectAcntIdOut": "java.lang.String",
    "selectAcntNoCrypIn": "sp.spa.cbc.dao.dto.SelectAcntNoCrypIn",
    "selectAcntNoCrypOut": "java.lang.String"
}

dbio_content = dbio_generator.generate(sql_calls, id_to_path_map, "SPAAcntInfoDao")
print(f"\n생성된 DBIO:")
print("-" * 40)
print(dbio_content)

# 파일로 저장
try:
    file_path = dbio_generator.write(dbio_content, "SPAAcntInfoDao")
    print(f"\n저장됨: {file_path}")
except Exception as e:
    print(f"\n저장 실패: {e}")


# ============================================================================
# shared_config 테스트
# ============================================================================
print("\n" + "=" * 80)
print("shared_config 테스트")
print("=" * 80)

from shared_config import (
    get_java_type,
    get_jdbc_type,
    get_mybatis_tag,
    snake_to_camel,
    struct_name_to_class_name,
)

print("\n타입 변환 테스트:")
for c_type in ["int", "char", "long", "double"]:
    java_type = get_java_type(c_type)
    jdbc_type = get_jdbc_type(c_type)
    print(f"  {c_type} → Java: {java_type}, JDBC: {jdbc_type}")

print("\nSQL 태그 변환 테스트:")
for sql_type in ["select", "insert", "update", "delete", "create"]:
    tag = get_mybatis_tag(sql_type)
    print(f"  {sql_type} → {tag}")

print("\n네이밍 변환 테스트:")
for name in ["user_name", "rfrn_strt_date", "spaa010p_inrec1"]:
    camel = snake_to_camel(name)
    class_name = struct_name_to_class_name(name)
    print(f"  {name} → camel: {camel}, class: {class_name}")

print("\n" + "=" * 80)
print("기본 테스트 완료!")
print("=" * 80)


# ============================================================================
# Variable Lineage Tracker 테스트
# ============================================================================
print("\n" + "=" * 80)
print("Variable Lineage Tracker 테스트")
print("=" * 80)

from variable_lineage import VariableLineageTracker
from variable_lineage.tracker import LineageConfig
import json
import os

# 트래커 생성
lineage_tracker = VariableLineageTracker(
    source_file="sample_input/enterprise_complex_sql.pc"
)

# 1. proc_parser 결과 추가
print("\n1. proc_parser 결과에서 노드 추가")
proc_node_count = lineage_tracker.add_from_proc_parser(elements)
print(f"   추가된 노드: {proc_node_count}개")

# 2. header_parser 결과 추가
print("\n2. header_parser 결과에서 노드 추가")
header_node_count = lineage_tracker.add_from_header_parser(db_vars_info)
print(f"   추가된 노드: {header_node_count}개")

# 3. dbio_generator SQL 추가
print("\n3. dbio_generator SQL에서 노드 추가")
dbio_node_count = lineage_tracker.add_from_dbio_generator(sql_calls, "SPAAcntInfoDao")
print(f"   추가된 노드: {dbio_node_count}개")

# 4. 연결관계 자동 구축
print("\n4. 노드 간 연결관계 구축")
link_count = lineage_tracker.build_links()
print(f"   생성된 링크: {link_count}개")

# 5. 그래프 요약
graph_dict = lineage_tracker.to_dict()
print("\n5. Lineage 그래프 요약:")
print(f"   총 노드 수: {graph_dict['summary']['total_nodes']}")
print(f"   총 링크 수: {graph_dict['summary']['total_links']}")
print(f"   노드 타입별:")
for node_type, count in graph_dict['summary']['nodes_by_type'].items():
    print(f"      {node_type}: {count}")

# 6. 변환 규칙이 적용된 링크 표시
print("\n6. 변환 규칙이 적용된 연결:")
links_with_transforms = [l for l in lineage_tracker.graph.links if l.transformations]
for link in links_with_transforms[:10]:
    source_node = lineage_tracker.graph.get_node(link.source_id)
    target_node = lineage_tracker.graph.get_node(link.target_id)
    if source_node and target_node:
        print(f"   {source_node.name} → {target_node.name}")
        print(f"      변환: {link.transformations}")
        print(f"      신뢰도: {link.confidence:.2f}")

# 7. 특정 변수 추적 쿼리
print("\n7. 변수 추적 쿼리 예시:")
query_result = lineage_tracker.query_lineage("acnt")
print(f"   'acnt' 검색 결과: {len(query_result['matched_nodes'])}개 노드")
for node in query_result['matched_nodes'][:5]:
    print(f"      - {node['name']} ({node['node_type']})")

# 8. JSON 파일로 저장
output_path = "./debug_output/lineage_graph.json"
try:
    os.makedirs("./debug_output", exist_ok=True)
    lineage_tracker.save_json(output_path)
    print(f"\n8. Lineage 그래프 저장됨: {output_path}")
except Exception as e:
    print(f"\n8. 저장 실패: {e}")

# 9. JSON 일부 출력
print("\n9. JSON 출력 미리보기 (처음 3개 노드):")
print("-" * 40)
preview_nodes = dict(list(graph_dict['nodes'].items())[:3])
preview_json = json.dumps(preview_nodes, indent=2, ensure_ascii=False)
print(preview_json[:800])
if len(preview_json) > 800:
    print("...")

print("\n" + "=" * 80)
print("Variable Lineage Tracker 테스트 완료!")
print("=" * 80)


# ============================================================================
# Neo4j Exporter 테스트
# ============================================================================
print("\n" + "=" * 80)
print("Neo4j Exporter 테스트")
print("=" * 80)

from variable_lineage import Neo4jExporter

# 1. 모든 프로그램 요소 노드 추가 (새 기능)
print("\n1. 프로그램 요소 노드 추가 (Headers, Macros, Functions, BamCalls)")
program_elements = lineage_tracker.add_all_program_elements(elements)
for element_type, count in program_elements.items():
    print(f"   {element_type}: {count}개")

# 2. Java 변수 노드 생성 (다대일 연결)
print("\n2. ProCVariable에서 JavaVariable 노드 생성")
java_count = lineage_tracker.add_java_variables()
print(f"   생성된 Java 변수: {java_count}개")

# 3. 그래프 요약 업데이트
graph_dict = lineage_tracker.to_dict()
print(f"\n3. 업데이트된 그래프 요약:")
print(f"   총 노드 수: {graph_dict['summary']['total_nodes']}")
print(f"   총 링크 수: {graph_dict['summary']['total_links']}")
print(f"   노드 타입별:")
for node_type, count in sorted(graph_dict['summary']['nodes_by_type'].items()):
    print(f"      {node_type}: {count}")

# 4. Neo4j Exporter 생성
program_name = "enterprise_complex_sql"
exporter = Neo4jExporter(program_name=program_name)

# 5. Cypher 파일 생성
cypher_path = "./debug_output/lineage_graph.cypher"
try:
    exporter.save_cypher(lineage_tracker.graph, cypher_path)
    print(f"\n4. Cypher 파일 저장됨: {cypher_path}")
except Exception as e:
    print(f"\n4. Cypher 저장 실패: {e}")

# 6. Cypher 미리보기
print("\n5. Cypher 미리보기 (새 노드 타입 포함):")
print("-" * 40)
cypher_content = exporter.to_cypher(lineage_tracker.graph)
print(cypher_content[:1000])
if len(cypher_content) > 1000:
    print("...")

# 6. MAPS_TO 관계 예시 (변환 규칙 포함)
print("\n5. MAPS_TO 관계 예시 (ProCVariable → JavaVariable):")
java_links = [l for l in lineage_tracker.graph.links 
              if l.target_id.startswith('java_var_') and l.transformations]
for link in java_links[:5]:
    source_node = lineage_tracker.graph.get_node(link.source_id)
    target_node = lineage_tracker.graph.get_node(link.target_id)
    if source_node and target_node:
        print(f"   {source_node.name} → {target_node.name}")
        print(f"      변환: {link.transformations}")

print("\n" + "=" * 80)
print("Neo4j Exporter 테스트 완료!")
print("=" * 80)


# ============================================================================
# Context Metadata Extractor 테스트
# ============================================================================
print("\n" + "=" * 80)
print("Context Metadata Extractor 테스트")
print("=" * 80)

from variable_lineage.context_extractor import ContextExtractor, FunctionContext
from variable_lineage.context_extractor.formatters import PromptFormatter

# 1. ContextExtractor 생성
print("\n1. ContextExtractor 초기화")
context_extractor = ContextExtractor(lineage_tracker, elements, db_vars_info)
print(f"   함수 수: {len(context_extractor.functions)}")
print(f"   변수 매핑 수: {len(context_extractor.var_mappings)}")

# 2. 함수 목록
print("\n2. 발견된 함수 목록:")
for func_name in list(context_extractor.functions.keys())[:5]:
    func = context_extractor.functions[func_name]
    print(f"   - {func_name}() [{func.get('line_start', 0)}-{func.get('line_end', 0)}]")

# 3. 첫 번째 함수 컨텍스트 추출
if context_extractor.functions:
    first_func = list(context_extractor.functions.keys())[0]
    print(f"\n3. 함수 '{first_func}' 컨텍스트 추출:")
    
    func_context = context_extractor.extract_function_context(first_func)
    if func_context:
        print(f"   - 로컬 변수: {len(func_context.local_variables)}개")
        print(f"   - 호스트 변수: {len(func_context.host_variables)}개")
        print(f"   - SQL 문: {len(func_context.sql_statements)}개")
        print(f"   - 변환 매핑: {len(func_context.variable_mappings)}개")
        
        # 4. LLM 프롬프트 생성
        print(f"\n4. LLM 프롬프트 생성 (Markdown 형식):")
        print("-" * 40)
        prompt = context_extractor.to_prompt(func_context, include_raw_content=False)
        print(prompt[:800])
        if len(prompt) > 800:
            print("...")
        
        # 5. Compact 형식
        print(f"\n5. Compact 형식:")
        print("-" * 40)
        formatter = PromptFormatter(format_type="compact")
        compact_prompt = formatter.format(func_context, include_source=False)
        print(compact_prompt[:500])
        if len(compact_prompt) > 500:
            print("...")
        
        # 6. JSON 출력
        print(f"\n6. JSON 출력:")
        print("-" * 40)
        json_output = context_extractor.to_json(func_context)
        print(json_output[:600])
        if len(json_output) > 600:
            print("...")

print("\n" + "=" * 80)
print("Context Metadata Extractor 테스트 완료!")
print("=" * 80)