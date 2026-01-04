from sql_extractor.pyparsing_parser import get_sql_parser

parser = get_sql_parser()

sql = "EXEC SQL SELECT name, age, HH12:MI:SS INTO :out_name, :out_age FROM users WHERE id = :in_id"

# SQL 타입 결정
sql_type = parser.determine_sql_type(sql)
print(f"SQL 타입: {sql_type}")  # "select"

# 호스트 변수 분류
input_vars, output_vars = parser.classify_host_variables(sql, sql_type)
print(f"입력 변수: {input_vars}")   # [':in_id']
print(f"출력 변수: {output_vars}")  # [':out_name', ':out_age']