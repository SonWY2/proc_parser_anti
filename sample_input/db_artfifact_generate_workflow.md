
# SQL → OMM → DBIO → DAO 변환 전체 과정

## 1. 전체 흐름도

```
[C 헤더 파일 (.h)]
        ↓
    [파싱 단계]
        ↓
[구조체 정보 추출]
        ↓
  [OMM 생성] ← [SQL 파싱 정보]
        ↓
  [DBIO 생성]
        ↓
   [DAO 생성]
```

---

## 2. 단계별 상세 과정

### Phase 1: 헤더 파일 파싱 (Header → OMM)

**입력**: `program.h` (C 헤더 파일)

**처리**:
1. **TypedefStructParser**: typedef 구조체 파싱
2. **STPStructParser**: STP 초기화 배열 파싱
3. `db_vars_info` 구조 생성

**출력**: 
- **SVC DTO**: `output/omm/program/svc/*.omm` (입출력 구조체)
- **DAO DTO**: `output/omm/program/dao/*.omm` (SQL 변수)

**생성되는 OMM 파일 예시**:
```
OMM com.example.svc.dto.SPAA01234In
<
 logicalName="SPAA01234In" description="SPAA01234In">
{
    Integer userId<length=10 description="사용자ID">;
    String userName<length=20 description="사용자명">;
    BigDecimal balance<length=15 decimal=2 description="잔액">;
}
```

---

### Phase 2: SQL 정보 결합 (SQL + variables.jsonl)

**입력**:
- `mybatis-sql_calls.yaml`: 파싱된 SQL 정보
  ```yaml
  - name: selectUser
    sql_type: select
    input_vars: [userId, userName]
    output_vars: [userId, userName, balance]
    parsed_sql: "SELECT user_id, user_name, balance FROM users WHERE..."
  ```
- `variables.jsonl`: 변수 메타데이터
  ```json
  {"name": "userId", "dtype": "int", "size": 10, "desc": "사용자ID"}
  ```

**처리**: `DAODTOGenerator`가 SQL별로 In/Out DTO 생성

**출력**:
- `SPAA0010DaoSelectUserIn.omm`
- `SPAA0010DaoSelectUserOut.omm`
- `id_to_path_map` (매핑 테이블)

---

### Phase 3: DBIO 생성 (OMM → MyBatis XML)

**입력**:
- OMM 파일들
- `mybatis-sql_calls.yaml`
- `variables.jsonl`
- `id_to_path_map`

**처리 과정**:

1. **SQL 타입 결정**:
```python
sql_type = SQL_TYPE_MAP[sql_obj["sql_type"]]
# "select" → "select"
# "insert" → "insert"
# "update" → "update"
# "delete" → "delete"
# "create" → "update" (DDL)
```

2. **DTO 경로 매핑**:
```python
parameter_type = "com.example.dao.dto.SPAA0010DaoSelectUserIn"
result_type = "com.example.dao.dto.SPAA0010DaoSelectUserOut"
```

3. **변수 처리**:
   - **JDBC 타입 추가**: `#{userId}` → `#{userId, jdbcType=INTEGER}`
   - **카멜케이스 변환**: `user_name` → `userName`
   - **XML 이스케이프**: `<`, `>` → `&lt;`, `&gt;`

**출력**: `SPAA0010Dao.dbio` (MyBatis XML)
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE mapper PUBLIC "-//mybatis.org//DTD Mapper 3.0//EN" "http://mybatis.org/dtd/mybatis-3-mapper.dtd">
<mapper namespace="com.example.dao.SPAA0010Dao">

<select id="selectUser" 
        parameterType="com.example.dao.dto.SPAA0010DaoSelectUserIn"
        resultType="com.example.dao.dto.SPAA0010DaoSelectUserOut">
    SELECT user_id, user_name, balance 
    FROM users 
    WHERE user_id = #{userId, jdbcType=INTEGER}
</select>

</mapper>
```

---

### Phase 4: DAO 생성 (DBIO → Java Interface)

**입력**:
- DBIO 파일 경로
- `id_to_path_map`
- 프로그램 매핑 정보

**처리**:

1. **Import 문 생성**:
```java
import com.example.dao.dto.SPAA0010DaoSelectUserIn;
import com.example.dao.dto.SPAA0010DaoSelectUserOut;
import java.util.List; // output_vars에 list_count가 있으면
```

2. **메서드 생성**:
```java
SPAA0010DaoSelectUserOut selectUser(
    SPAA0010DaoSelectUserIn spaa0010DaoSelectUserIn
);
```

3. **리스트 처리**:
- `output_vars`에 `list_count`가 있으면 → `List<OutDTO>`

**출력**: `SPAA0010Dao.java`
```java
package com.example.dao;

import bxm.common.annotaion.BxmCategory;
import bxm.container.annotation.BxmDataAccess;
import com.example.dao.dto.SPAA0010DaoSelectUserIn;
import com.example.dao.dto.SPAA0010DaoSelectUserOut;

@BxmDataAccess(mapper = "SPAA0010Dao.dbio", datasource = "MainDS")
@BxmCategory(logicalName="", description="", author="")
public interface SPAA0010Dao {
    
    @BxmCategory(logicalName="", description="", author="")
    SPAA0010DaoSelectUserOut selectUser(
        SPAA0010DaoSelectUserIn spaa0010DaoSelectUserIn
    );
}
```

---

## 3. 핵심 변환 규칙

### 타입 변환
| C 타입 | Java 타입 | JDBC 타입 |
|--------|-----------|-----------|
| `int` | `Integer` | `INTEGER` |
| `char` | `String` | `VARCHAR` |
| `long` | `BigDecimal` | `NUMERIC` |
| `double` | `Integer` | `DECIMAL` |

### 명명 규칙
- **변수명**: `user_name` → `userName` (camelCase)
- **DTO명**: `{DAO이름}{SQL이름}{In/Out}`
- **DAO명**: `{프로그램명}Dao`

### 특수 처리
1. **DDL (CREATE/DROP/ALTER/TRUNCATE)**:
   - `parameterType`, `resultType` 없음
   - MyBatis `<update>` 태그 사용

2. **List 타입**:
   - `list_count` 존재 시 → `List<DTO>`

3. **없는 출력**:
   - SELECT → `String`
   - 기타 → `int`

---

## 4. 파일 구조

```
output/
├── omm/
│   └── program_name/
│       ├── svc/
│       │   ├── SPAA01234In.omm
│       │   └── SPAA01234Out.omm
│       └── dao/
│           ├── SPAA0010DaoSelectUserIn.omm
│           └── SPAA0010DaoSelectUserOut.omm
├── dbio/
│   └── program_name/
│       └── dao/
│           └── SPAA0010Dao.dbio
└── dao/
    └── program_name/
        └── SPAA0010Dao.java
```

---

이것이 **C 헤더 + SQL → Java 변환**의 전체 흐름입니다.
