---
name: file-reader-chunker
description: |
  파일을 읽고, 대용량(5,000 LOC 이상) 파일의 경우 함수 경계를 감지하여 청킹.
  
  **When to use**: 분석 대상 파일을 읽을 때 항상 사용. LOC를 자동 측정하여 청킹 여부 결정.

inputs:
  - name: file_path
    type: string
    required: true
    description: 읽을 파일 경로
  
  - name: force_chunk
    type: boolean
    required: false
    default: false
    description: 강제 청킹 여부 (5,000 LOC 미만이어도 청킹)

outputs:
  - name: chunks
    type: json
    required: true
    description: 청킹된 파일 조각 배열
---

# File Reader & Chunker Skill

파일을 읽고 필요시 함수 경계 기준으로 청킹하는 스킬입니다.

---

## 📋 What it does

1. **파일 전체 읽기** (소용량 파일)
2. **함수 시작 패턴 탐지**: `int/void/char + 함수명 + (` 패턴으로 경계 감지
3. **5,000 LOC 이상 시 함수 단위로 분할**
4. **청크 간 컨텍스트 유지**: 전역 변수, 직전 함수 시그니처 포함

---

## 🔧 활용 기존 코드

| 모듈 | 파일 경로 | 용도 |
|------|----------|------|
| file_handler | `parsing/core/file_handler.py` | 파일 읽기 |
| chunking utils | `infra/agents/langchain/utils/chunking.py` | 청킹 로직 (이미 존재!) |

---

## 💻 구현 예시

```python
from infra.agents.langchain.utils.chunking import chunk_by_function

def file_reader_chunker(file_path: str, force_chunk: bool = False) -> dict:
    """
    파일을 읽고 필요시 청킹
    
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
                    "context_header": str,  # 전역 변수, 이전 함수 시그니처
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

## 📊 I/O Contract

### Input Example

```json
{
  "file_path": "src/customer.pc",
  "force_chunk": false
}
```

### Output Example

```json
{
  "file_path": "src/customer.pc",
  "total_loc": 7200,
  "chunked": true,
  "chunks": [
    {
      "chunk_id": 1,
      "start_line": 1,
      "end_line": 850,
      "boundary_type": "function",
      "boundary_name": "get_customer_info",
      "context_header": "/* global vars: g_config, g_conn */",
      "content": "..."
    },
    {
      "chunk_id": 2,
      "start_line": 851,
      "end_line": 1700,
      "boundary_type": "function",
      "boundary_name": "update_customer_status",
      "context_header": "/* global vars: g_config */\n/* prev: int get_customer_info() */",
      "content": "..."
    }
  ]
}
```

---

## ⚠️ Edge Cases

### 1. 함수 경계 탐지 실패
- **증상**: 함수 시작 패턴을 찾을 수 없음
- **폴백**: LOC 기준 1,000줄 단위로 분할
- **처리**: `boundary_type: "loc"` 플래그 설정

### 2. 단일 함수가 1,000 LOC 초과
- **증상**: 하나의 함수가 너무 큼
- **폴백**: 해당 함수 내 블록 단위(`{}`) 기준 재분할
- **처리**: `boundary_type: "block"` 플래그 설정

### 3. 바이너리/인코딩 오류
- **증상**: UTF-8 디코딩 실패
- **처리**: 오류 메시지와 함께 null 반환
- **응답**:
  ```json
  {
    "error": "Encoding error: ...",
    "file_path": "...",
    "chunks": null
  }
  ```

---

## ✅ 검증 체크리스트

- [ ] 5,000 LOC 미만 파일이 단일 청크로 반환되는가?
- [ ] 5,000 LOC 이상 파일이 함수 경계로 청킹되는가?
- [ ] 각 청크에 `context_header`가 포함되는가?
- [ ] 청크 ID가 순차적으로 증가하는가?
- [ ] 전체 라인 수 합계가 원본 파일과 일치하는가?
