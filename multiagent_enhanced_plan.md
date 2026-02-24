# Pro*C → Java Spring/MyBatis 멀티에이전트 시스템 - Enhanced Plan v2.0

> **기존 코드베이스 활용 중심 설계**
> multiagent_implement_plan.md를 기반으로, 프로젝트의 기존 모듈을 최대한 활용하여 구현 복잡도를 줄이고 안정성을 높입니다.

---

## 📋 개요

| 항목 | 내용 |
|------|------|
| **대상 사용자** | Pro*C → Java 전환 작업 수행 개발자 |
| **시스템 목적** | 레거시 C/Pro*C 코드를 Java Spring + MyBatis로 자동 변환 |
| **핵심 차별점** | **기존 프로덕션 검증 코드 재사용** (parsing, conversion, generation 모듈) |
| **산출물** | Java Spring 코드, MyBatis 파일셋, 마이그레이션 리포트 |

---

## 🎯 Agent 설계 (Enhanced)

### 1. main-orchestrator

**역할**: 전체 파이프라인 조율, 사용자 확인, 작업 분배

**구현 기반**:
- `infra/agents/langchain/orchestrator.py` 패턴 참고
- `infra/agents/base/orchestrator.py` 워크플로우 활용

**주요 책임**:
1. 사용자에게 리팩토링 여부 확인 (블로킹)
2. STRATEGY 결정 (preserve | refactor)
3. Sub-agent 호출 및 결과 통합
4. 최종 리포트 생성

**입력**:
```python
{
    "header_paths": ["include/types.h", "include/customer.h"],
    "proc_paths": ["src/customer.pc", "src/order.pc"],
    "knowledge_doc_path": "docs/domain-rules.md",  # Optional
    "output_base_path": "output/"
}
```

**출력**:
```python
{
    "status": "success",
    "strategy": "preserve",  # or "refactor"
    "java_files": [...],
    "mybatis_files": [...],
    "report_path": "output/report/migration-report.md",
    "extern_stub_count": 5,
    "manual_review_count": 3
}
```

---

### 2. analysis-agent

**역할**: 코드 구조 분석, 메타데이터 추출

**활용 기존 코드**:
- ✅ `parsing/core/core.py` → **ProCParser**: Pro*C 파일 파싱
- ✅ `parsing/header/integrated_parser.py` → **IntegratedHeaderParser**: 헤더 분석
- ✅ `parsing/sql/extractor.py` → **SQLExtractor**: SQL 추출
- ✅ `analysis/cpg/cpg_builder.py` → **CPGBuilder**: 의존성 그래프 생성
- ✅ `analysis/lineage/tracker.py` → **VariableLineageTracker**: 변수 추적

**처리 절차**:
```python
# 1. 헤더 파일 분석 (매크로, typedef, struct)
from parsing.header import IntegratedHeaderParser
parser = IntegratedHeaderParser(include_paths=["./include"])
header_result = parser.parse_headers(header_paths)
type_map = header_result.macros  # C 타입 → Java 타입 매핑

# 2. Pro*C 파일 파싱 (LOC 확인 후 청킹)
from parsing.core import ProCParser
proc_parser = ProCParser()

for pc_file in proc_paths:
    loc = count_lines(pc_file)

    if loc >= 5000:
        # 청킹 필요 (file-reader-chunker SKILL 호출)
        chunks = file_reader_chunker.chunk_by_function(pc_file)
        for chunk in chunks:
            elements = proc_parser.parse_content(chunk['content'])
            # 청크별 분석 후 병합
    else:
        # 단일 분석
        elements = proc_parser.parse_file(pc_file)

# 3. SQL 추출
from parsing.sql import SQLExtractor
sql_extractor = SQLExtractor()
code, sql_blocks = sql_extractor.decompose_sql(code, file_key, program_dict)
```

**출력 형식** (analysis_result):
```json
{
  "type_map": {
    "CHAR_100": "String",
    "CUSTOMER": "CustomerDto"
  },
  "files": [
    {
      "source_file": "src/customer.pc",
      "loc": 7200,
      "chunked": true,
      "functions": [
        {
          "name": "get_customer_info",
          "signature": "int get_customer_info(char *cust_id, CUSTOMER *out)",
          "summary": "고객 ID로 고객 정보 조회",
          "sql_refs": ["sql_001"],
          "calls": ["log_error"],
          "is_extern": false,
          "parseable": true
        }
      ]
    }
  ],
  "sql_blocks": [
    {
      "id": "sql_001",
      "source_file": "src/customer.pc",
      "function": "get_customer_info",
      "sql_type": "SELECT",
      "raw_sql": "SELECT ID, NAME FROM CUSTOMER WHERE ID = :in_id",
      "bind_vars": ["in_id"],
      "output_vars": ["cust_id", "cust_name"],
      "is_cursor": false,
      "is_dynamic": false
    }
  ],
  "extern_list": [
    {
      "name": "g_config",
      "type": "CONFIG_T",
      "declared_in": "globals.h",
      "used_in": ["src/customer.pc:120"]
    }
  ]
}
```

---

### 3. java-spring-agent

**역할**: Java Spring 코드 생성 (Controller/Service 계층)

**활용 기존 코드**:
- ✅ `conversion/core.py` → **ProcToJavaConverter**: Pro*C → Java 변환기
- ✅ `conversion/plugins/naming_convention.py` → **Naming 플러그인**: snake_case → camelCase
- ✅ `conversion/plugins/spring_annotation.py` → **Spring 어노테이션 플러그인**

**구현 절차**:
```python
from conversion.core import ProcToJavaConverter
from conversion.plugins import NamingConventionPlugin, SpringAnnotationPlugin
from validation.llm import LLMClient

# LLM 클라이언트 초기화
llm_client = LLMClient()

# 변환기 초기화
converter = ProcToJavaConverter(llm_client, config)
converter.register_plugin(NamingConventionPlugin())

if strategy == "refactor":
    # 리팩토링 모드: Spring 패턴 적용
    converter.register_plugin(SpringAnnotationPlugin())

# 변환 실행
result = converter.convert(analysis_result)

# Extern Stub 생성
for extern_item in analysis_result['extern_list']:
    stub_code = generate_stub(extern_item)
    write_file(f"output/stubs/{extern_item['name']}.java", stub_code)
```

**출력 예시**:
```java
// AUTO-GENERATED: source=customer.pc
// STRATEGY: preserve

package com.modernized.service;

import org.springframework.stereotype.Service;
import org.springframework.beans.factory.annotation.Autowired;

@Service
public class CustomerService {

    // STUB: extern from globals.h - g_config (CONFIG_T)
    private ConfigStub gConfig = new ConfigStub();

    @Autowired
    private CustomerMapper customerMapper;

    /**
     * 원본: get_customer_info(char *cust_id, CUSTOMER *out)
     * 위치: customer.pc:45
     */
    public CustomerDto getCustomerInfo(String custId) {
        return customerMapper.selectCustomerById(custId);
    }
}
```

---

### 4. mybatis-agent

**역할**: MyBatis DTO/DAO/XML 생성

**활용 기존 코드**:
- ✅ `parsing/sql/mybatis_converter.py` → **MyBatisConverter**: Pro*C SQL → MyBatis XML
- ✅ `generation/artifacts/dao_generator.py` → **DAOGenerator**: DAO 인터페이스 생성
- ✅ `generation/artifacts/omm_generator.py` → **OMMGenerator**: DTO 클래스 생성
- ✅ `generation/artifacts/dbio_generator.py` → **DBIOGenerator**: XML Mapper 생성

**구현 절차**:
```python
from parsing.sql import MyBatisConverter
from generation.artifacts import DAOGenerator, OMMGenerator, DBIOGenerator

# MyBatis 변환
converter = MyBatisConverter()
mybatis_sqls = []

for sql_block in analysis_result['sql_blocks']:
    mybatis_sql = converter.convert_sql(
        sql=sql_block['raw_sql'],
        sql_type=sql_block['sql_type'],
        sql_id=sql_block['id'],
        input_vars=sql_block['bind_vars'],
        output_vars=sql_block['output_vars']
    )
    mybatis_sqls.append(mybatis_sql)

# DTO 생성 (OMMGenerator)
omm_gen = OMMGenerator(base_package="com.modernized.dto")
for sql in mybatis_sqls:
    if sql.output_fields:
        dto_code = omm_gen.generate_from_sql(sql)
        write_file(f"output/dto/{sql.id}Dto.java", dto_code)

# DAO 인터페이스 생성 (DAOGenerator)
dao_gen = DAOGenerator(base_package="com.modernized.mapper")
dao_code = dao_gen.generate(mybatis_sqls, {}, "CustomerMapper")
write_file("output/mapper/CustomerMapper.java", dao_code)

# MyBatis XML 생성 (DBIOGenerator)
dbio_gen = DBIOGenerator()
xml_code = dbio_gen.generate(mybatis_sqls, namespace="com.modernized.mapper.CustomerMapper")
write_file("output/mapper/CustomerMapper.xml", xml_code)
```

**출력 예시 (DTO)**:
```java
// AUTO-GENERATED: source=customer.pc, sql_id=sql_001
package com.modernized.dto;

public class CustomerDto {
    private String custId;
    private String custName;

    // getters/setters...
}
```

**출력 예시 (MyBatis XML)**:
```xml
<!-- AUTO-GENERATED: source=customer.pc, sql_id=sql_001 -->
<mapper namespace="com.modernized.mapper.CustomerMapper">
  <select id="selectCustomerById" parameterType="String" resultType="CustomerDto">
    SELECT ID AS custId, NAME AS custName
    FROM CUSTOMER
    WHERE ID = #{custId}
  </select>
</mapper>
```

---

### 5. report-agent

**역할**: 마이그레이션 리포트 생성

**신규 구현** (간단한 템플릿 기반):
```python
from datetime import datetime

def generate_report(
    strategy: str,
    java_files: list,
    mybatis_files: list,
    extern_list: list,
    manual_review_items: list
) -> str:
    """마이그레이션 리포트 생성"""

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    report = f"""# Migration Report
생성일: {timestamp}
전략: {strategy}

## 1. 변환 요약
| 항목 | 수량 |
|------|------|
| 생성 Java 파일 | {len(java_files)} |
| 생성 MyBatis XML | {len(mybatis_files)} |
| Extern Stub 생성 | {len(extern_list)} |
| 수동 검토 필요 | {len(manual_review_items)} |

## 2. 파일 매핑
| 원본 파일 | 생성 파일 |
|----------|----------|
"""

    for java_file in java_files:
        report += f"| {java_file['source']} | {java_file['output']} |\n"

    report += """
## 3. 요주의 항목

### 3-1. Extern Stub 목록
| 변수/함수명 | 원본 위치 | 생성 Stub | 권장 조치 |
|------------|----------|----------|----------|
"""

    for extern in extern_list:
        report += f"| {extern['name']} | {extern['declared_in']} | {extern['stub_file']} | 실제 구현으로 교체 필요 |\n"

    report += """
## 4. 검증 체크리스트
- [ ] 모든 EXEC SQL이 MyBatis XML로 추출되었는가
- [ ] Extern Stub이 실제 구현으로 교체되었는가
- [ ] 동적 SQL 로직이 의도대로 변환되었는가
- [ ] @Transactional 경계가 올바르게 설정되었는가
"""

    return report
```

---

## 🛠️ Skills 설계 (Enhanced)

### Skill 1: file-reader-chunker

**활용 기존 코드**:
- ✅ `parsing/core/file_handler.py` → 파일 읽기
- ✅ `infra/agents/langchain/utils/chunking.py` → 청킹 로직 (이미 존재!)

**구현**:
```python
# infra/agents/langchain/utils/chunking.py 활용
from infra.agents.langchain.utils.chunking import chunk_by_tokens, chunk_by_function

def file_reader_chunker(file_path: str, force_chunk: bool = False) -> dict:
    """
    파일을 읽고 필요시 청킹

    Args:
        file_path: 파일 경로
        force_chunk: 강제 청킹 여부

    Returns:
        {
            "file_path": str,
            "total_loc": int,
            "chunked": bool,
            "chunks": [
                {
                    "chunk_id": int,
                    "start_line": int,
                    "end_line": int,
                    "boundary_type": "function",  # or "loc"
                    "boundary_name": str,  # 함수명
                    "content": str
                }
            ]
        }
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    total_loc = content.count('\n') + 1

    # 5,000 LOC 미만 → 단일 청크
    if total_loc < 5000 and not force_chunk:
        return {
            "file_path": file_path,
            "total_loc": total_loc,
            "chunked": False,
            "chunks": [
                {
                    "chunk_id": 0,
                    "start_line": 1,
                    "end_line": total_loc,
                    "boundary_type": "single",
                    "boundary_name": None,
                    "content": content
                }
            ]
        }

    # 청킹 로직 (함수 경계 기준)
    chunks = chunk_by_function(content, max_size=1000)

    return {
        "file_path": file_path,
        "total_loc": total_loc,
        "chunked": True,
        "chunks": chunks
    }
```

---

### Skill 2: macro-type-mapper

**활용 기존 코드**:
- ✅ `parsing/header/integrated_parser.py` → **IntegratedHeaderParser**
- ✅ `parsing/header/macro_extractor.py` → **MacroExtractor**
- ✅ `infra/config/type_mappings.py` → C → Java 타입 매핑 테이블

**구현**:
```python
from parsing.header import IntegratedHeaderParser
from infra.config.type_mappings import C_TO_JAVA_TYPE_MAP

def macro_type_mapper(header_paths: list) -> dict:
    """
    C 헤더에서 typedef/struct/macro 추출 후 Java 타입으로 매핑

    Args:
        header_paths: 헤더 파일 경로 리스트

    Returns:
        {
            "type_map": {
                "CHAR_100": "String",
                "CUSTOMER": "CustomerDto"
            },
            "constants": [
                {
                    "c_name": "MAX_RETRY",
                    "value": "3",
                    "java_candidate": "static final int MAX_RETRY = 3"
                }
            ],
            "struct_candidates": [
                {
                    "c_struct": "CUSTOMER",
                    "fields": [...],
                    "java_class": "CustomerDto"
                }
            ]
        }
    """
    parser = IntegratedHeaderParser()
    result = parser.parse_headers(header_paths)

    # 매크로 → Java 상수 변환
    constants = []
    for macro_name, macro_value in result.macros.items():
        java_type = infer_java_type(macro_value)
        constants.append({
            "c_name": macro_name,
            "value": str(macro_value),
            "java_candidate": f"static final {java_type} {macro_name} = {macro_value}"
        })

    # typedef → Java 타입 매핑
    type_map = {}
    for c_type, java_type in C_TO_JAVA_TYPE_MAP.items():
        type_map[c_type] = java_type

    # struct → DTO 후보 생성
    struct_candidates = []
    for struct_name, struct_info in result.db_vars_info.items():
        struct_candidates.append({
            "c_struct": struct_name,
            "fields": struct_info.get('fields', []),
            "java_class": f"{struct_name}Dto"
        })

    return {
        "type_map": type_map,
        "constants": constants,
        "struct_candidates": struct_candidates
    }
```

---

### Skill 3: sql-extractor

**활용 기존 코드**:
- ✅ `parsing/sql/extractor.py` → **SQLExtractor** (Tree-sitter 기반)
- ✅ `parsing/sql/cursor_merger.py` → **CursorMerger**: 커서 병합
- ✅ `parsing/sql/dynamic_sql_extractor.py` → **DynamicSQLExtractor**: 동적 SQL 추출

**구현**:
```python
from parsing.sql import SQLExtractor

def sql_extractor(proc_chunk: str, source_file: str, function_name: str = None) -> dict:
    """
    Pro*C 청크에서 SQL 추출 및 정제

    Args:
        proc_chunk: Pro*C 코드 조각
        source_file: 원본 파일명
        function_name: 함수명 (Optional)

    Returns:
        {
            "sql_blocks": [
                {
                    "id": "sql_001",
                    "source_file": "customer.pc",
                    "function": "get_customer_info",
                    "sql_type": "SELECT",
                    "raw_sql": "SELECT ID, NAME FROM CUSTOMER WHERE ID = :in_id",
                    "bind_vars": ["in_id"],
                    "output_vars": ["cust_id", "cust_name"],
                    "is_cursor": false,
                    "is_dynamic": false
                }
            ]
        }
    """
    extractor = SQLExtractor()

    # Tree-sitter 기반 SQL 추출
    sql_blocks = extractor._extract_with_tree_sitter(proc_chunk)

    result_blocks = []
    for i, block in enumerate(sql_blocks):
        # SQL 타입 결정
        sql_type_result = extractor.sql_type_registry.determine_type(block.text)

        # 호스트 변수 추출
        input_vars, output_vars = extractor.host_var_registry.classify_by_direction(
            block.text, sql_type_result.value
        )

        result_blocks.append({
            "id": f"sql_{i}",
            "source_file": source_file,
            "function": function_name or block.containing_function,
            "sql_type": sql_type_result.value,
            "raw_sql": block.text.lstrip(),
            "bind_vars": [v.get('raw', '') for v in input_vars],
            "output_vars": [v.get('raw', '') for v in output_vars],
            "is_cursor": sql_type_result.metadata.get('is_cursor', False) if sql_type_result.metadata else False,
            "is_dynamic": False  # DynamicSQLExtractor로 별도 탐지 필요
        })

    return {"sql_blocks": result_blocks}
```

---

### Skill 4: file-writer

**간단한 신규 구현**:
```python
import os
from pathlib import Path
from datetime import datetime

def file_writer(output_path: str, content: str, overwrite: bool = True) -> dict:
    """
    파일 저장

    Args:
        output_path: 저장 경로
        content: 파일 내용
        overwrite: 덮어쓰기 여부

    Returns:
        {
            "success": bool,
            "output_path": str,
            "message": str
        }
    """
    try:
        # 디렉토리 생성
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        # 파일 존재 확인
        if os.path.exists(output_path) and not overwrite:
            # 타임스탬프 추가
            base, ext = os.path.splitext(output_path)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"{base}.conflict.{timestamp}{ext}"

        # 저장
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)

        return {
            "success": True,
            "output_path": output_path,
            "message": "File saved successfully"
        }

    except Exception as e:
        return {
            "success": False,
            "output_path": output_path,
            "message": f"Error: {str(e)}"
        }
```

---

## 🔄 워크플로우 (Enhanced)

```
[사용자 입력]
  header_paths: ["include/types.h"]
  proc_paths: ["src/customer.pc"]
  output_base_path: "output/"
        │
        ▼
[main-orchestrator]
  ① AskUserQuestion: "리팩토링 포함 여부 O/X?" → 사용자 응답 대기 (블로킹)
        │
        ▼ (O/X 수신)
  ② STRATEGY 결정 (refactor | preserve)
        │
        ▼
[analysis-agent 호출]
  ③-A. macro-type-mapper SKILL 호출
       → IntegratedHeaderParser로 헤더 분석
       → type_map 생성
        │
  ③-B. 각 Pro*C 파일마다:
       → LOC 측정
       → 5,000+ LOC: file-reader-chunker SKILL로 청킹
       → ProCParser로 파싱
       → sql-extractor SKILL로 SQL 추출
        │
  ③-C. 전체 결과 통합 → analysis_result 생성
        │
        ▼
[병렬 호출]
  ④-A. java-spring-agent 호출
       → ProcToJavaConverter 사용
       → Spring 코드 생성 + Extern Stub 생성
        │
  ④-B. mybatis-agent 호출
       → MyBatisConverter 사용
       → DAOGenerator, OMMGenerator로 DTO/DAO 생성
       → DBIOGenerator로 XML 생성
        │
        ▼ (양쪽 완료)
[report-agent 호출]
  ⑤ 변환 로그, extern 목록, stub 목록 수집
     → 마이그레이션 리포트 생성
        │
        ▼
[main-orchestrator 완료 보고]
  ⑥ 사용자에게 산출물 경로 목록 출력
```

---

## 📊 기존 코드 활용 매핑표

| Agent/Skill | 활용 모듈 | 파일 경로 |
|-------------|----------|----------|
| **analysis-agent** | ProCParser | `parsing/core/core.py` |
| | IntegratedHeaderParser | `parsing/header/integrated_parser.py` |
| | MacroExtractor | `parsing/header/macro_extractor.py` |
| | SQLExtractor | `parsing/sql/extractor.py` |
| | CPGBuilder | `analysis/cpg/cpg_builder.py` |
| **java-spring-agent** | ProcToJavaConverter | `conversion/core.py` |
| | NamingConventionPlugin | `conversion/plugins/naming_convention.py` |
| | SpringAnnotationPlugin | `conversion/plugins/spring_annotation.py` |
| **mybatis-agent** | MyBatisConverter | `parsing/sql/mybatis_converter.py` |
| | DAOGenerator | `generation/artifacts/dao_generator.py` |
| | OMMGenerator | `generation/artifacts/omm_generator.py` |
| | DBIOGenerator | `generation/artifacts/dbio_generator.py` |
| **file-reader-chunker** | chunking utils | `infra/agents/langchain/utils/chunking.py` |
| **macro-type-mapper** | IntegratedHeaderParser | `parsing/header/integrated_parser.py` |
| | type mappings | `infra/config/type_mappings.py` |
| **sql-extractor** | SQLExtractor | `parsing/sql/extractor.py` |
| | CursorMerger | `parsing/sql/cursor_merger.py` |
| | DynamicSQLExtractor | `parsing/sql/dynamic_sql_extractor.py` |

---

## 🚀 구현 우선순위

### Phase 1: Skills 구현 (기존 코드 Wrapper)
1. ✅ **file-reader-chunker** (chunking.py 활용)
2. ✅ **macro-type-mapper** (integrated_parser.py 활용)
3. ✅ **sql-extractor** (extractor.py 활용)
4. ✅ **file-writer** (신규 간단 구현)

### Phase 2: Agent 구현
1. ✅ **analysis-agent** (Skills 조합)
2. ✅ **java-spring-agent** (ProcToJavaConverter 활용)
3. ✅ **mybatis-agent** (생성기 3종 활용)
4. ✅ **report-agent** (신규 템플릿 구현)

### Phase 3: Orchestrator 구현
1. ✅ **main-orchestrator** (langchain orchestrator 패턴 활용)
2. ✅ 사용자 확인 플로우 (AskUserQuestion 통합)
3. ✅ 병렬 실행 로직 (asyncio 활용)

### Phase 4: 검증 및 최적화
1. ✅ 통합 테스트 (샘플 Pro*C 파일)
2. ✅ Extern 처리 검증
3. ✅ 대용량 파일 청킹 검증 (5,000+ LOC)
4. ✅ 리포트 품질 검증

---

## 📝 사용 예시

### CLI 실행
```bash
# Agent 시스템 실행
python -m infra.agents.langchain --mode multiagent

# 또는 직접 호출
python run_multiagent_conversion.py \
  --headers include/types.h,include/customer.h \
  --procs src/customer.pc,src/order.pc \
  --output output/ \
  --knowledge docs/domain-rules.md
```

### Python API 사용
```python
from infra.agents.langchain.orchestrator import MultiAgentOrchestrator

orchestrator = MultiAgentOrchestrator()

result = orchestrator.run(
    header_paths=["include/types.h", "include/customer.h"],
    proc_paths=["src/customer.pc"],
    knowledge_doc_path="docs/domain-rules.md",
    output_base_path="output/"
)

print(f"변환 완료: {result['status']}")
print(f"Java 파일: {len(result['java_files'])}개")
print(f"MyBatis 파일: {len(result['mybatis_files'])}개")
print(f"리포트: {result['report_path']}")
```

---

## 🔧 설정 파일 예시

### config/multiagent_config.yaml
```yaml
# 멀티에이전트 시스템 설정
agents:
  main_orchestrator:
    model: gpt-4-turbo
    temperature: 0.2

  analysis_agent:
    model: gpt-3.5-turbo
    max_chunk_size: 1000
    enable_cpg: true

  java_spring_agent:
    model: gpt-4-turbo
    temperature: 0.3
    default_strategy: preserve  # preserve | refactor
    base_package: com.modernized

  mybatis_agent:
    model: gpt-3.5-turbo
    base_package: com.modernized.mapper
    dto_package: com.modernized.dto

skills:
  file_reader_chunker:
    max_loc_threshold: 5000
    chunk_size: 1000
    boundary_type: function  # function | loc

  sql_extractor:
    use_tree_sitter: true
    enable_cursor_merge: true
    enable_dynamic_sql: true

output:
  base_path: output/
  java_path: output/java/
  mybatis_path: output/mybatis/
  report_path: output/report/
```

---

## ✅ 검증 체크리스트

### Agent 동작 검증
- [ ] main-orchestrator가 사용자 확인 없이 진행하지 않음
- [ ] analysis-agent가 5,000 LOC 이상 파일을 청킹함
- [ ] java-spring-agent가 extern stub을 생성함
- [ ] mybatis-agent가 DTO/DAO/XML 3종을 모두 생성함
- [ ] report-agent가 리포트에 extern 목록을 포함함

### Skill 동작 검증
- [ ] file-reader-chunker가 함수 경계 기준 청킹함
- [ ] macro-type-mapper가 typedef를 Java 타입으로 변환함
- [ ] sql-extractor가 커서를 병합하여 처리함
- [ ] file-writer가 충돌 시 타임스탬프 파일을 생성함

### 품질 기준
- [ ] 모든 EXEC SQL이 MyBatis XML로 변환됨
- [ ] Extern 참조가 모두 리포트에 기록됨
- [ ] 리팩토링 전략이 일관되게 적용됨
- [ ] 산출 파일이 지정 경로에 저장됨

---

## 🎯 다음 단계

1. **.claude/agents/ 디렉토리 구조 생성**
   ```
   .claude/agents/
   ├── main-orchestrator.md
   ├── analysis-agent.md
   ├── java-spring-agent.md
   ├── mybatis-agent.md
   └── report-agent.md
   ```

2. **.skills/ 디렉토리 구조 생성**
   ```
   .skills/
   ├── file-reader-chunker/
   │   └── SKILL.md
   ├── macro-type-mapper/
   │   └── SKILL.md
   ├── sql-extractor/
   │   └── SKILL.md
   └── file-writer/
       └── SKILL.md
   ```

3. **통합 테스트 시나리오 작성**
   - 단일 파일 변환 (LOC < 5,000)
   - 대용량 파일 변환 (LOC > 5,000)
   - Extern 참조 포함 파일
   - 커서 사용 파일

4. **LangGraph 이식 준비**
   - Agent 인터페이스 JSON 스키마 정의
   - 노드 변환 매핑 문서 작성

---

**최종 검토**: ✅ 기존 프로덕션 코드 최대 활용, 구현 복잡도 최소화, LangGraph 이식 가능
