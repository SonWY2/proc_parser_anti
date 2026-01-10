
# STPStructParser 파싱 결과 구조

## 입력 (C 코드)
```c
typedef struct {
    int user_id;
    char user_name[20];
    double balance;
} user_info_t;

user_info_stp = {
    'i', 10, 0, 0,
    'o', 20, 0, 0,
    'd', 15, 2, 0,
    '\0', 0, 0, 0
};
```

## 파싱 후 출력 (db_vars_info)
```python
{
    "user_info_t": {
        "userId": {
            "dtype": "Integer",
            "size": 10,           # STP에서 가져옴 (v1)
            "decimal": 0,
            "name": "user_id",
            "org_name": "user_id"
        },
        "userName": {
            "dtype": "String",
            "size": 20,           # STP에서 가져옴 (v1)
            "decimal": 0,
            "name": "user_name",
            "org_name": "user_name"
        },
        "balance": {
            "dtype": "BigDecimal",
            "size": 15,           # STP에서 가져옴 (v1)
            "decimal": 2,         # STP에서 가져옴 (v2)
            "name": "balance",
            "org_name": "balance"
        }
    }
}
```

## 핵심 정리 규칙

### 1. 구조체명 매핑
- STP 이름: `xxx_stp` → 구조체명: `xxx_t`
- 예: `user_info_stp` → `user_info_t`

### 2. 필드명 변환
- **원본**: `user_name` (snake_case)
- **변환**: `userName` (camelCase)
- 딕셔너리 키로 사용

### 3. 타입 변환
| C 타입 | Java 타입 |
|--------|-----------|
| `int` | `Integer` |
| `char` | `String` |
| `long` | `BigDecimal` |
| `double` | `Integer` |

### 4. 크기/소수점 업데이트
- **size**: STP의 v1 값으로 덮어쓰기
- **decimal**: STP의 v2 값 (0이 아닐 때만 업데이트)

### 5. 중첩 구조체 평탄화
```c
typedef struct {
    int sub_id;
    char sub_name[5];
} sub_t;

typedef struct {
    int main_id;
    sub_t sub_data;  // 중첩
} main_t;
```

**평탄화 결과**:
```python
{
    "main_t": {
        "mainId": {...},
        "subData": {...}      # sub_t 타입 그대로
    },
    "sub_t": {
        "subId": {...},       # parent_type: "sub_t"로 표시
        "subName": {...}
    }
}
```

## 최종 구조 (필수 필드)
```python
{
    "구조체명_t": {
        "camelCaseFieldName": {
            "dtype": "Java타입",
            "size": 정수,
            "decimal": 정수 (선택),
            "name": "원본_필드명",
            "org_name": "원본_필드명"
        }
    }
}
```

이 구조는 이후 OMM 파일 생성 시 그대로 사용됩니다.
