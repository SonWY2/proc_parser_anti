# Translation Merge 모듈 사용법

Pro*C → Java 변환 결과물을 하나의 완전한 Java 클래스로 병합합니다.

## 설치

```python
from translation_merge import TranslationMerger, MethodTranslation
```

## 기본 사용법

```python
from translation_merge import TranslationMerger, MethodTranslation

merger = TranslationMerger()

# 클래스 스켈레톤 (LLM 생성)
class_skeleton = """
package com.example;

import java.util.List;

public class MyProgram {
}
"""

# 메소드 변환 결과들 (LLM 생성)
method_translations = [
    MethodTranslation(
        name="processData",
        llm_response='''
import java.util.ArrayList;
import java.util.Map;

public void processData() {
    List<String> data = new ArrayList<>();
    // 비즈니스 로직
}

// LLM이 생성한 다른 코드...
'''
    ),
    MethodTranslation(
        name="saveResult",
        llm_response='''
import java.io.File;

public void saveResult(String path) {
    File file = new File(path);
    // 저장 로직
}
'''
    ),
]

# 병합 실행
result = merger.merge(class_skeleton, method_translations)

# 결과 확인
print(result.merged_code)    # 병합된 Java 코드
print(result.imports)        # 수집된 import 목록
print(result.methods)        # 병합된 메소드 이름들
print(result.warnings)       # 경고 메시지 (메소드 못찾음 등)
```

## 출력 예시

```java
package com.example;

import java.io.File;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

public class MyProgram {

    public void processData() {
        List<String> data = new ArrayList<>();
        // 비즈니스 로직
    }

    public void saveResult(String path) {
        File file = new File(path);
        // 저장 로직
    }

}
```

## 주요 기능

| 기능 | 설명 |
|------|------|
| 메소드 추출 | LLM 응답에서 지정된 이름의 메소드만 추출 |
| Import 병합 | 모든 import 수집, 중복 제거, 정렬 (java.* → javax.* → 기타) |
| 본문 삽입 | 클래스 본문 내 적절한 위치에 메소드 삽입 |

## 에러 처리

메소드를 찾지 못한 경우 `warnings`에 메시지가 추가됩니다:

```python
if result.warnings:
    for warning in result.warnings:
        print(f"경고: {warning}")
```
