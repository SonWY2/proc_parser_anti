# Pro*C to Java Conversion Module

LLM을 활용하여 Pro*C/SQC 파일을 Java(Spring+MyBatis)로 변환하는 모듈입니다.

## 주요 기능

- **2단계 변환 프로세스**:
  1. **Skeleton 생성**: 클래스 구조 (패키지, 임포트, 필드, 메서드 시그니처)
  2. **Function 변환**: 각 Pro*C 함수를 Java 메서드로 1:1 변환

- **플러그인 시스템**: 변환 프로세스를 확장 가능한 hook 제공

## 빠른 시작

### CLI 사용

```bash
# 전체 변환
python convert_to_java.py original_source.sqc -o ./output/

# 스켈레톤만 생성
python convert_to_java.py original_source.sqc --skeleton-only

# 특정 함수만 변환
python convert_to_java.py original_source.sqc --function tlfb000m_main

# 프롬프트만 확인 (LLM 호출 없이 stdout 출력)
python convert_to_java.py original_source.sqc --prompt-only

# 프롬프트 파일 내보내기 (Markdown 파일로 저장)
# 전체 (스켈레톤 + 모든 함수)
python convert_to_java.py original_source.sqc --export-prompts ./prompts/

# 특정 함수만 내보내기
python convert_to_java.py original_source.sqc --function tlfb000m_main --export-prompts ./prompts/

# 스켈레톤만 내보내기
python convert_to_java.py original_source.sqc --skeleton-only --export-prompts ./prompts/
```

### Python API 사용

```python
from conversion import ProcToJavaConverter, ConversionConfig
from conversion.plugins import NamingConventionPlugin
from validation.llm import LLMClient
from parsing.core import UnifiedMetadataGenerator

# 1. 메타데이터 생성
generator = UnifiedMetadataGenerator()
metadata = generator.generate("original_source.sqc")

# 2. 변환기 설정
config = ConversionConfig(
    package_name="com.example.service",
    class_name_suffix="Service",
    use_spring_annotations=True,
)

# 3. 변환 실행
llm_client = LLMClient()
converter = ProcToJavaConverter(llm_client, config)
converter.register_plugin(NamingConventionPlugin())

result = converter.convert(metadata)

# 4. 결과 사용
print(result.full_java_code)
print(f"변환된 함수: {result.converted_functions}/{result.total_functions}")
```

## 설정 옵션

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `package_name` | `com.example.service` | Java 패키지명 |
| `class_name_suffix` | `Service` | 클래스명 접미사 |
| `use_spring_annotations` | `True` | Spring 어노테이션 사용 |
| `mybatis_mapper_package` | `com.example.mapper` | MyBatis Mapper 패키지 |
| `temperature` | `0.3` | LLM 응답 온도 |
| `max_tokens` | `4096` | 최대 토큰 수 |

## 플러그인

### 내장 플러그인

- **NamingConventionPlugin**: snake_case → camelCase 변환
- **SpringAnnotationPlugin**: @Service, @Slf4j, @Transactional 추가

### 커스텀 플러그인 작성

```python
from conversion.plugin_interface import ConversionPlugin
from conversion.types import SkeletonResult, ConversionConfig

class MyPlugin(ConversionPlugin):
    def post_skeleton(self, result: SkeletonResult, config: ConversionConfig) -> SkeletonResult:
        # 스켈레톤 결과 수정
        result.java_code = result.java_code.replace("// TODO", "// FIXME")
        return result
```

## 환경 설정

LLM API를 사용하려면 `.env` 파일에 다음 설정이 필요합니다:

```env
OPENAI_API_KEY=your-api-key
OPENAI_API_BASE=https://api.openai.com/v1
OPENAI_MODEL=gpt-4
```

## 의존성

이 모듈은 다음 내부 모듈에 의존합니다:

- `parsing.core.UnifiedMetadataGenerator`: 메타데이터 생성
- `validation.llm.LLMClient`: LLM API 호출
