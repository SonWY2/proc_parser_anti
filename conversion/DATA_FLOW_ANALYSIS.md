# Pro*C to Java 변환 - 입력 데이터 분석

LLM 프롬프트 생성 시 Class Skeleton과 Function 변환에 각각 어떤 정보가 입력되는지 설명합니다.

---

## 1. 전체 데이터 흐름

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Pro*C/SQC 소스 파일                                  │
│                      (예: original_source.sqc)                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    UnifiedMetadataGenerator                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 파싱 결과:                                                           │   │
│  │  • comments, includes, macros                                       │   │
│  │  • sql, variables, functions                                        │   │
│  │  • function_prototypes, function_calls, bam_calls                   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                          metadata.json (output.json)
                                    │
                    ┌───────────────┴───────────────┐
                    │                               │
                    ▼                               ▼
┌──────────────────────────────┐    ┌──────────────────────────────┐
│     Step 1: Skeleton         │    │     Step 2: Functions        │
│  (클래스 구조 생성)           │    │  (메서드 구현)               │
└──────────────────────────────┘    └──────────────────────────────┘
                    │                               │
                    ▼                               ▼
         SkeletonResult                   FunctionConversionResult[]
                    │                               │
                    └───────────────┬───────────────┘
                                    ▼
                           Full Java Code (.java)
```

---

## 2. Class Skeleton 생성 - 입력 데이터

Class Skeleton 프롬프트에는 **전체 파일 수준**의 정보가 입력됩니다.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      SKELETON PROMPT 입력 데이터                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 1. SOURCE FILE INFO                                                 │   │
│  │    • source_file: "original_source.sqc"                             │   │
│  │    → 클래스명 추론: OriginalSourceService                            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 2. GLOBAL VARIABLES                                                 │   │
│  │    (function == null 인 변수들)                                      │   │
│  │    ┌───────────────────────────────────────────────────────────┐    │   │
│  │    │ • long H_iacnt_id           → private Long iacntId        │    │   │
│  │    │ • char H_ibsns_date[9]      → private String ibsnsDate    │    │   │
│  │    │ • long H_oftrs_opts...      → private Long oftrsOpts...   │    │   │
│  │    │ • ...                                                     │    │   │
│  │    └───────────────────────────────────────────────────────────┘    │   │
│  │    → Java 클래스 필드로 변환                                         │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 3. FUNCTION PROTOTYPES                                              │   │
│  │    ┌───────────────────────────────────────────────────────────┐    │   │
│  │    │ static int tlfb000m_main(tlfb000m_in_t*, tlfb000m_out_t*) │    │   │
│  │    │ static int tlfb000m_a000_initialize(void)                 │    │   │
│  │    │ static int tlfb000m_a500_input_check(void)                │    │   │
│  │    │ static int tlfb000m_c000_event_process(void)              │    │   │
│  │    │ ...                                                       │    │   │
│  │    └───────────────────────────────────────────────────────────┘    │   │
│  │    → Java 메서드 시그니처로 변환 (구현 없이 선언만)                    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 4. SQL SUMMARY                                                      │   │
│  │    (전체 SQL 통계)                                                   │   │
│  │    ┌───────────────────────────────────────────────────────────┐    │   │
│  │    │ • SELECT: 3 statements                                    │    │   │
│  │    │ • UPDATE: 2 statements                                    │    │   │
│  │    │ • INSERT: 1 statement                                     │    │   │
│  │    └───────────────────────────────────────────────────────────┘    │   │
│  │    → MyBatis Mapper 의존성 파악                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 5. HEADER DEPENDENCIES                                              │   │
│  │    ┌───────────────────────────────────────────────────────────┐    │   │
│  │    │ • #include "afc_bam.h"                                    │    │   │
│  │    │ • #include "tlfb000m.h"                                   │    │   │
│  │    │ • #include "mba0360m.h"                                   │    │   │
│  │    └───────────────────────────────────────────────────────────┘    │   │
│  │    → 외부 의존성/Mapper 임포트 결정                                   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Skeleton 프롬프트 출력 예시

```java
package com.example.service;

import org.springframework.stereotype.Service;
import lombok.extern.slf4j.Slf4j;
// ... imports ...

@Service
@Slf4j
public class OriginalSourceService {
    
    // Fields (from global variables)
    private Long iacntId;
    private String ibsnsDate;
    // ...
    
    // Method signatures (from prototypes)
    private int main(/* params */) { /* TODO */ }
    private int a000Initialize() { /* TODO */ }
    private int a500InputCheck() { /* TODO */ }
    // ...
}
```

---

## 3. Function 변환 - 입력 데이터

각 Function 프롬프트에는 **해당 함수 범위** 내의 정보가 입력됩니다.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      FUNCTION PROMPT 입력 데이터                             │
│              (예: tlfb000m_c000_event_process 함수)                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 1. FUNCTION METADATA                                                │   │
│  │    • name: "tlfb000m_c000_event_process"                            │   │
│  │    • java_name: "c000EventProcess" (camelCase)                      │   │
│  │    • line_start: 301                                                │   │
│  │    • line_end: 540                                                  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 2. DOCSTRING (원본 주석)                                            │   │
│  │    ┌───────────────────────────────────────────────────────────┐    │   │
│  │    │ /* ================================================       │    │   │
│  │    │  * 업무 처리                                              │    │   │
│  │    │  * ================================================ */   │    │   │
│  │    └───────────────────────────────────────────────────────────┘    │   │
│  │    → Javadoc 변환                                                    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 3. RAW CONTENT (함수 전체 소스)                                     │   │
│  │    ┌───────────────────────────────────────────────────────────┐    │   │
│  │    │ static int tlfb000m_c000_event_process(void) {            │    │   │
│  │    │     BAM_START;                                            │    │   │
│  │    │     if (strcmp(H_ia_acnt_ifnm_updt_yn, "Y") == 0) {       │    │   │
│  │    │         if (tlfb000m_c100_update_...) != SUCC) {          │    │   │
│  │    │             BAM_RETURN_FAIL;                              │    │   │
│  │    │         }                                                 │    │   │
│  │    │     }                                                     │    │   │
│  │    │     // ... 비즈니스 로직 ...                               │    │   │
│  │    │     BAM_RETURN_SUCC;                                      │    │   │
│  │    │ }                                                         │    │   │
│  │    └───────────────────────────────────────────────────────────┘    │   │
│  │    → 핵심 변환 대상                                                  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 4. SQL IN THIS FUNCTION                                             │   │
│  │    (function == "tlfb000m_c000_event_process" 인 SQL)               │   │
│  │    ┌───────────────────────────────────────────────────────────┐    │   │
│  │    │ 없음 (이 함수는 직접 SQL 없음, 다른 함수 호출)             │    │   │
│  │    └───────────────────────────────────────────────────────────┘    │   │
│  │    → MyBatis mapper 메서드 호출로 변환                               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 5. LOCAL VARIABLES                                                  │   │
│  │    (function == "tlfb000m_c000_event_process" 인 변수)              │   │
│  │    ┌───────────────────────────────────────────────────────────┐    │   │
│  │    │ • long m1, m2 (중간 계산용)                               │    │   │
│  │    │ • long s (합계)                                           │    │   │
│  │    │ ...                                                       │    │   │
│  │    └───────────────────────────────────────────────────────────┘    │   │
│  │    → Java 지역 변수로 선언                                           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 6. CALLED FUNCTIONS                                                 │   │
│  │    (function == "tlfb000m_c000_event_process" 인 function_calls)    │   │
│  │    ┌───────────────────────────────────────────────────────────┐    │   │
│  │    │ • tlfb000m_c100_update_meg_ftrs_wthd_blnc()               │    │   │
│  │    │ • tlfb000m_c200_select_meg_ftrs_wthd_blnc()               │    │   │
│  │    │ • tlfb000m_c210_bamcall_mbe1210m()                        │    │   │
│  │    │ • strcmp()                                                │    │   │
│  │    │ • COPYS(), ELOG(), ILOG()                                 │    │   │
│  │    └───────────────────────────────────────────────────────────┘    │   │
│  │    → 내부 메서드 호출/유틸리티 호출로 변환                            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 7. CONTEXT (from Skeleton)                                          │   │
│  │    ┌───────────────────────────────────────────────────────────┐    │   │
│  │    │ 사용 가능한 클래스 필드:                                   │    │   │
│  │    │ • private Long iacntId                                    │    │   │
│  │    │ • private String ibsnsDate                                │    │   │
│  │    │ • private String iaAcntIfnmUpdtYn                         │    │   │
│  │    │ ...                                                       │    │   │
│  │    └───────────────────────────────────────────────────────────┘    │   │
│  │    → 전역 변수 접근 시 필드 참조                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. 데이터 매핑 요약 테이블

### Skeleton 입력 데이터

| 메타데이터 필드 | 추출 위치 | 용도 |
|----------------|----------|------|
| `metadata.source_file` | 루트 | 클래스명 추론 |
| `elements_by_type.variables` (function=null) | source_analysis | 클래스 필드 |
| `elements_by_type.function_prototypes` | source_analysis | 메서드 시그니처 |
| `elements_by_type.sql` (통계) | source_analysis | Mapper 의존성 |
| `header_tree.direct_includes` | 루트 | 외부 의존성 |

### Function 입력 데이터

| 메타데이터 필드 | 추출 조건 | 용도 |
|----------------|----------|------|
| `functions[i].name` | 대상 함수 | 메서드명 |
| `functions[i].raw_content` | 대상 함수 | 변환 대상 코드 |
| `functions[i].docstring` | 대상 함수 | Javadoc |
| `sql[*]` | `function == 함수명` | SQL → Mapper call |
| `variables[*]` | `function == 함수명` | 지역 변수 |
| `function_calls[*]` | `function == 함수명` | 내부 호출 |
| `SkeletonResult.fields` | 컨텍스트 | 필드 참조 |

---

## 5. 변환 규칙 (LLM에 전달되는 지침)

```
┌───────────────────────────────────────────────────────────────────┐
│                      변환 규칙                                     │
├───────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Pro*C 요소              →      Java 요소                         │
│  ─────────────────────────────────────────────────────────────── │
│  char[N]                 →      String                           │
│  long                    →      Long / long                      │
│  int                     →      int / Integer                    │
│  ─────────────────────────────────────────────────────────────── │
│  EXEC SQL SELECT...      →      mapper.selectXxx(...)            │
│  EXEC SQL UPDATE...      →      mapper.updateXxx(...)            │
│  EXEC SQL INSERT...      →      mapper.insertXxx(...)            │
│  ─────────────────────────────────────────────────────────────── │
│  BAMCALL(module,...)     →      moduleService.call(...)          │
│  BAM_RETURN_SUCC         →      return SUCCESS                   │
│  BAM_RETURN_FAIL         →      return FAIL / throw Exception    │
│  ─────────────────────────────────────────────────────────────── │
│  ELOG("msg", args)       →      log.error("msg", args)           │
│  ILOG("msg", args)       →      log.info("msg", args)            │
│  ─────────────────────────────────────────────────────────────── │
│  switch(SQLCODE)         →      try-catch or if-else             │
│  SQLNOTFOUND             →      결과 null 또는 Optional.empty()   │
│  ─────────────────────────────────────────────────────────────── │
│  strcmp(a, b) == 0       →      a.equals(b)                      │
│  memset(ptr, 0, size)    →      (초기화 또는 생략)                 │
│  memcpy(dst, src, n)     →      dst = src (또는 System.arraycopy) │
│  COPYS(dst, src)         →      dst = src                        │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
```

---

## 6. 실제 프롬프트 예시 (축약)

### Skeleton Prompt 예시

```markdown
## Task: Pro*C to Java Class Skeleton Conversion

### Source File: `original_source.sqc`
### Target Class: `com.example.service.OriginalSourceService`

### Global Variables (→ Class Fields):
```c
long H_iacnt_id;
char H_ibsns_date[9];
long H_oftrs_opts_wtdw_psbl_tamt;
...
```

### Function Prototypes (→ Method Signatures):
```c
static int tlfb000m_main(tlfb000m_in_t *pIn, tlfb000m_out_t *pOut);
static int tlfb000m_a000_initialize(void);
...
```

### Required Output:
Generate a Java class skeleton with package, imports, fields, method stubs.
```

### Function Prompt 예시

```markdown
## Task: Pro*C Function to Java Method Conversion

### Function: `tlfb000m_c000_event_process` → `c000EventProcess`

### Original Pro*C Code:
```c
static int tlfb000m_c000_event_process(void) {
    BAM_START;
    if (strcmp(H_ia_acnt_ifnm_updt_yn, "Y") == 0) {
        if (tlfb000m_c100_update_meg_ftrs_wthd_blnc() != SUCC) {
            BAM_RETURN_FAIL;
        }
    }
    // ...
}
```

### Called Functions:
- tlfb000m_c100_update_meg_ftrs_wthd_blnc()
- tlfb000m_c200_select_meg_ftrs_wthd_blnc()
- strcmp()

### Conversion Instructions:
1. Convert C types to Java types
2. Replace embedded SQL with MyBatis mapper method calls
...
```
