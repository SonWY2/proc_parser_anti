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

---

## 플러그인 시스템

병합 시 자동으로 적용되는 후처리 플러그인:

| 플러그인 | phase | target | priority | 설명 |
|----------|-------|--------|----------|------|
| `visibility` | PRE_MERGE | METHOD | 30 | public → private 변환 (main 제외) |
| `bxmcategory` | PRE_MERGE | METHOD | 50 | @bxmcategory 어노테이션 자동 추가 |
| `main_deduplicator` | POST_MERGE | CODE | 200 | 중복 main 함수 제거 (마지막만 유지) |

### Phase와 Target

| Phase | 설명 | 사용할 메소드 |
|-------|------|--------------|
| `PRE_MERGE` | 코드 조립 **전** (메소드 단위) | `process()`, `process_all()` |
| `POST_MERGE` | 코드 조립 **후** (전체 코드) | `process_code()` |

| Target | 설명 |
|--------|------|
| `METHOD` | 개별 메소드 단위 처리 |
| `CODE` | 전체 병합 코드 처리 |

### 플러그인 활성화/비활성화

```python
# 기본: 모든 플러그인 활성화
merger = TranslationMerger()

# 전체 플러그인 비활성화
merger = TranslationMerger(use_plugins=False)
```

### 특정 플러그인만 선택 적용

```python
from translation_merge import TranslationMerger, list_plugins

# 등록된 플러그인 목록 확인
print(list_plugins())  # ['bxmcategory', 'main_deduplicator', 'visibility']

# 원하는 플러그인만 적용
result = merger.merge(
    skeleton, 
    translations,
    plugin_names=["bxmcategory"]  # 어노테이션만 적용
)
```

### 새 플러그인 추가 방법

`translation_merge/plugins/` 폴더에 새 파일을 추가하면 자동 등록됩니다:

```python
# translation_merge/plugins/my_plugin.py
from . import register_plugin
from .base import MergePlugin, PluginPhase, PluginTarget

@register_plugin
class MyPlugin(MergePlugin):
    name = "my_plugin"
    priority = 40
    description = "내 플러그인"
    phase = PluginPhase.PRE_MERGE   # PRE_MERGE | POST_MERGE | BOTH
    target = PluginTarget.METHOD    # METHOD | CODE
    
    def process(self, method):
        # PRE_MERGE + METHOD 플러그인용
        return method
    
    def process_code(self, code):
        # POST_MERGE + CODE 플러그인용
        return code
```

### 플러그인 삭제

플러그인 파일 삭제 또는 `@register_plugin` 데코레이터 제거 시 자동으로 비활성화됩니다.

---

## 고급: Phase/Target 조율

### Phase별 플러그인 직접 로딩

```python
from translation_merge import load_plugins_by_phase, PluginPhase

# PRE_MERGE 플러그인만 로드
pre_plugins = load_plugins_by_phase(PluginPhase.PRE_MERGE)
print([p.name for p in pre_plugins])  # ['visibility', 'bxmcategory']

# POST_MERGE 플러그인만 로드
post_plugins = load_plugins_by_phase(PluginPhase.POST_MERGE)
print([p.name for p in post_plugins])  # ['main_deduplicator']

# 특정 플러그인만 필터링
post_plugins = load_plugins_by_phase(
    PluginPhase.POST_MERGE, 
    plugin_names=["main_deduplicator"]
)
```

### 플러그인 조합 예시

```python
# 어노테이션만 추가 (visibility, main_deduplicator 제외)
result = merger.merge(skeleton, translations, plugin_names=["bxmcategory"])

# main 중복 제거만 (다른 변환 없이)
result = merger.merge(skeleton, translations, plugin_names=["main_deduplicator"])

# 모든 플러그인 비활성화 후 수동 적용
merger = TranslationMerger(use_plugins=False)
result = merger.merge(skeleton, translations)

# 수동으로 POST_MERGE 플러그인만 적용
for plugin in load_plugins_by_phase(PluginPhase.POST_MERGE):
    result.merged_code = plugin.process_code(result.merged_code)
```

### 커스텀 플러그인에서 Phase/Target 선택 가이드

| 사용 케이스 | Phase | Target | 구현 메소드 |
|------------|-------|--------|------------|
| 개별 메소드 변환 | `PRE_MERGE` | `METHOD` | `process()` |
| 메소드 필터링/정렬 | `PRE_MERGE` | `METHOD` | `process_all()` |
| 전체 코드 검사/변환 | `POST_MERGE` | `CODE` | `process_code()` |
| 스켈레톤+메소드 통합 처리 | `POST_MERGE` | `CODE` | `process_code()` |

### BOTH Phase 사용

```python
@register_plugin
class DualPhasePlugin(MergePlugin):
    name = "dual_phase"
    phase = PluginPhase.BOTH  # PRE와 POST 모두 실행
    target = PluginTarget.METHOD
    
    def process(self, method):
        # PRE_MERGE 단계에서 실행
        return method
    
    def process_code(self, code):
        # POST_MERGE 단계에서 실행
        return code
```



