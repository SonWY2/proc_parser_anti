---
name: file-writer
description: |
  생성된 코드/문서를 지정 경로에 저장. 디렉토리 자동 생성 포함.
  
  **When to use**: 모든 agent가 산출물을 파일로 저장할 때 호출.

inputs:
  - name: output_path
    type: string
    required: true
    description: 저장할 파일 경로
  
  - name: content
    type: string
    required: true
    description: 파일 내용
  
  - name: overwrite
    type: boolean
    required: false
    default: true
    description: 덮어쓰기 여부

outputs:
  - name: result
    type: json
    required: true
    description: 저장 결과 (성공/실패, 경로)
---

# File Writer Skill

파일을 지정 경로에 저장하고 결과를 반환합니다.

---

## 📋 What it does

1. **경로의 중간 디렉토리 자동 생성**
2. **파일 저장 및 성공/실패 결과 반환**
3. **overwrite=false 시 기존 파일 존재하면 타임스탬프 추가**

---

## 💻 구현 예시

```python
import os
from pathlib import Path
from datetime import datetime

def file_writer(output_path: str, content: str, overwrite: bool = True) -> dict:
    """
    파일 저장
    
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

## 📊 I/O Contract

### Input Example

```json
{
  "output_path": "output/java/CustomerService.java",
  "content": "package com.modernized.service;\n\npublic class CustomerService {...}",
  "overwrite": true
}
```

### Output Example (Success)

```json
{
  "success": true,
  "output_path": "output/java/CustomerService.java",
  "message": "File saved successfully"
}
```

### Output Example (Conflict - overwrite=false)

```json
{
  "success": true,
  "output_path": "output/java/CustomerService.conflict.20260224_103045.java",
  "message": "File saved successfully (conflict resolved with timestamp)"
}
```

### Output Example (Error)

```json
{
  "success": false,
  "output_path": "/invalid/path/file.java",
  "message": "Error: Permission denied"
}
```

---

## ⚠️ Edge Cases

### 1. 경로 권한 오류

**증상**: 디렉토리 생성 또는 파일 쓰기 권한 없음
**처리**:
```json
{
  "success": false,
  "output_path": "/root/protected/file.java",
  "message": "Error: Permission denied - /root/protected/"
}
```

**권장 조치**: main-orchestrator에 보고 후 대체 경로 사용

### 2. overwrite 충돌

**증상**: overwrite=false이고 파일이 이미 존재
**처리**: `{filename}.conflict.{timestamp}` 형식으로 저장
**예시**:
- 원본: `CustomerService.java`
- 저장: `CustomerService.conflict.20260224_103045.java`

### 3. 디스크 공간 부족

**증상**: 파일 쓰기 중 디스크 공간 부족
**처리**:
```json
{
  "success": false,
  "output_path": "output/large_file.xml",
  "message": "Error: No space left on device"
}
```

---

## ✅ 검증 체크리스트

- [ ] 중간 디렉토리가 자동 생성되는가?
- [ ] overwrite=true일 때 기존 파일이 덮어써지는가?
- [ ] overwrite=false일 때 타임스탬프가 추가되는가?
- [ ] 권한 오류 시 적절한 에러 메시지가 반환되는가?
- [ ] UTF-8 인코딩이 올바르게 적용되는가?
