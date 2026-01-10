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
print("테스트 완료!")
print("=" * 80)