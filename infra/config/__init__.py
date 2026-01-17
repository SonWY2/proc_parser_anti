"""
shared_config 모듈
공통 타입 매핑, SQL 매핑, 네이밍 규칙 등을 중앙 관리합니다.
"""

from .type_mappings import (
    C_TO_JAVA_TYPE_MAP,
    STP_NUMERIC_TYPES,
    STP_SKIP_TYPES,
    STP_TYPE_TO_JAVA,
    get_java_type,
    get_jdbc_type,
)

from .sql_mappings import (
    SQL_TYPE_TO_MYBATIS_TAG,
    DDL_TYPES,
    DEFAULT_RESULT_TYPES,
    get_mybatis_tag,
    is_ddl,
    get_default_result_type,
)

from .naming_rules import (
    COUNT_FIELD_PATTERNS,
    PRIMITIVE_TYPES,
    snake_to_camel,
    camel_to_pascal,
    find_count_field,
    is_primitive_type,
    is_custom_struct,
    struct_name_to_class_name,
)

from .logger import (
    logger,
    get_logger,
    setup_file_logging,
    LogStage,
    log_step,
)

__all__ = [
    # type_mappings
    "C_TO_JAVA_TYPE_MAP",
    "STP_NUMERIC_TYPES",
    "STP_SKIP_TYPES",
    "STP_TYPE_TO_JAVA",
    "get_java_type",
    "get_jdbc_type",
    # sql_mappings
    "SQL_TYPE_TO_MYBATIS_TAG",
    "DDL_TYPES",
    "DEFAULT_RESULT_TYPES",
    "get_mybatis_tag",
    "is_ddl",
    "get_default_result_type",
    # naming_rules
    "COUNT_FIELD_PATTERNS",
    "PRIMITIVE_TYPES",
    "snake_to_camel",
    "camel_to_pascal",
    "find_count_field",
    "is_primitive_type",
    "is_custom_struct",
    "struct_name_to_class_name",
    # logger
    "logger",
    "get_logger",
    "setup_file_logging",
    "LogStage",
    "log_step",
]
