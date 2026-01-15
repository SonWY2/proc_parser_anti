"""
SQL 변환기 별칭 테스트 모듈입니다.
SQLConverter가 네이밍 컨벤션 플러그인을 사용하여 호스트 변수에 별칭을 올바르게 지정하는지 테스트합니다.
"""
import unittest
from sql_converter import SQLConverter
from plugins.naming_convention import SnakeToCamelPlugin

class TestSQLConverterAliasing(unittest.TestCase):
    def setUp(self):
        self.plugin = SnakeToCamelPlugin()
        self.converter = SQLConverter(naming_convention=self.plugin)

    def test_basic_aliasing(self):
        sql = "SELECT * FROM users WHERE id = :user_id"
        result = self.converter.normalize_sql(sql)
        self.assertIn(":user_id AS userId", result['normalized_sql'])
        self.assertEqual(result['input_host_vars'], [':user_id'])

    def test_multiple_vars(self):
        sql = "INSERT INTO users (id, name) VALUES (:user_id, :user_name)"
        result = self.converter.normalize_sql(sql)
        self.assertIn(":user_id AS userId", result['normalized_sql'])
        self.assertIn(":user_name AS userName", result['normalized_sql'])

    def test_robustness_strings(self):
        # :fake_var inside string should not be aliased
        sql = "SELECT ':fake_var' FROM dual WHERE id = :real_var"
        result = self.converter.normalize_sql(sql)
        self.assertIn("':fake_var'", result['normalized_sql'])
        self.assertNotIn(":fake_var AS", result['normalized_sql'])
        self.assertIn(":real_var AS realVar", result['normalized_sql'])

    def test_robustness_comments(self):
        # :fake_var inside comment should not be aliased
        sql = "SELECT * FROM users WHERE id = :real_var -- :fake_var"
        result = self.converter.normalize_sql(sql)
        self.assertIn(":real_var AS realVar", result['normalized_sql'])
        # The comment might be preserved or stripped depending on implementation, 
        # but it definitely shouldn't be aliased.
        # My implementation preserves comments.
        self.assertIn("-- :fake_var", result['normalized_sql'])
        self.assertNotIn(":fake_var AS", result['normalized_sql'])

    def test_robustness_multiline_comments(self):
        sql = "SELECT /* :fake_var */ * FROM users WHERE id = :real_var"
        result = self.converter.normalize_sql(sql)
        self.assertIn("/* :fake_var */", result['normalized_sql'])
        self.assertIn(":real_var AS realVar", result['normalized_sql'])

    def test_into_clause_removal(self):
        # Output vars in INTO clause should be extracted but removed from SQL string
        sql = "SELECT name INTO :user_name FROM users WHERE id = :user_id"
        result = self.converter.normalize_sql(sql)
        self.assertIn(":user_id AS userId", result['normalized_sql'])
        self.assertNotIn(":user_name", result['normalized_sql']) # Should be removed
        self.assertEqual(result['output_host_vars'], [':user_name'])

    def test_time_edge_case(self):
        # 12:00:00 should not be treated as host var :00
        sql = "SELECT '2023-01-01 12:00:00' FROM dual"
        result = self.converter.normalize_sql(sql)
        # It's in a string, so it should be handled by string logic.
        # But what if it's not in a string? (Invalid SQL but parser shouldn't crash or misidentify)
        # My regex handles strings first.
        self.assertIn("'2023-01-01 12:00:00'", result['normalized_sql'])
        self.assertEqual(len(result['input_host_vars']), 0)

    def test_complex_nested_sql(self):
        sql = """
        SELECT * FROM (
            SELECT /* inner comment :fake */ col1, ':string :fake'
            FROM t1
            WHERE c = :inner_var
        ) WHERE d = :outer_var
        """
        result = self.converter.normalize_sql(sql)
        self.assertIn(":inner_var AS innerVar", result['normalized_sql'])
        self.assertIn(":outer_var AS outerVar", result['normalized_sql'])
        self.assertIn("/* inner comment :fake */", result['normalized_sql'])
        self.assertIn("':string :fake'", result['normalized_sql'])

    def test_comment_before_sql_type(self):
        """주석이 SQL 문 앞에 있어도 올바른 타입 감지"""
        sql = "/* 주석 */ SELECT * FROM users"
        result = self.converter.normalize_sql(sql)
        self.assertEqual(result['sql_type'], 'SELECT')
        
        sql2 = "-- 주석\nSELECT * FROM users"
        result2 = self.converter.normalize_sql(sql2)
        self.assertEqual(result2['sql_type'], 'SELECT')

    def test_exec_sql_removed(self):
        """EXEC SQL이 normalized_sql에서 제거되는지 확인"""
        sql = "EXEC SQL SELECT * FROM users WHERE id = :user_id"
        result = self.converter.normalize_sql(sql)
        self.assertNotIn("EXEC SQL", result['normalized_sql'])
        self.assertIn("SELECT", result['normalized_sql'])
        self.assertEqual(result['sql_type'], 'SELECT')

    def test_indicator_variable(self):
        """인디케이터 변수 (:var:ind) 처리"""
        converter = SQLConverter()  # naming_convention 없이
        sql = "SELECT name INTO :emp_name:emp_name_ind FROM employees"
        result = converter.normalize_sql(sql)
        self.assertIn(':emp_name', result['output_host_vars'])
        self.assertIn(':emp_name_ind', result['output_host_vars'])
        
        sql2 = "INSERT INTO t VALUES (:val:val_ind)"
        result2 = converter.normalize_sql(sql2)
        self.assertIn(':val', result2['input_host_vars'])
        self.assertIn(':val_ind', result2['input_host_vars'])

    def test_array_host_variable(self):
        """배열 호스트 변수 (:arr[i]) 처리"""
        converter = SQLConverter()
        sql = "INSERT INTO t VALUES (:arr[i], :name[idx])"
        result = converter.normalize_sql(sql)
        self.assertIn(':arr[i]', result['input_host_vars'])
        self.assertIn(':name[idx]', result['input_host_vars'])

    def test_semicolon_stripped(self):
        """세미콜론이 기본적으로 제거되는지 확인"""
        sql = "SELECT * FROM users;"
        result = self.converter.normalize_sql(sql)
        self.assertFalse(result['normalized_sql'].endswith(';'))

    def test_semicolon_preserved(self):
        """strip_semicolon=False일 때 세미콜론 유지"""
        converter = SQLConverter(strip_semicolon=False)
        sql = "SELECT * FROM users;"
        result = converter.normalize_sql(sql)
        self.assertTrue(result['normalized_sql'].endswith(';'))

    def test_for_array_dml(self):
        """FOR :array_size INSERT 구문 처리"""
        converter = SQLConverter()
        sql = "EXEC SQL FOR :count INSERT INTO t VALUES (:id, :name)"
        result = converter.normalize_sql(sql)
        self.assertEqual(result['sql_type'], 'INSERT')
        self.assertIn(':count', result['input_host_vars'])
        self.assertNotIn('FOR', result['normalized_sql'].upper().split()[0])

    def test_additional_sql_types(self):
        """추가된 SQL 타입 감지"""
        test_cases = [
            ("CREATE TABLE t (id INT)", "CREATE"),
            ("DROP TABLE t", "DROP"),
            ("TRUNCATE TABLE t", "TRUNCATE"),
            ("MERGE INTO t USING s ON (t.id = s.id)", "MERGE"),
            ("WHENEVER SQLERROR CONTINUE", "WHENEVER"),
        ]
        converter = SQLConverter()
        for sql, expected_type in test_cases:
            result = converter.normalize_sql(sql)
            self.assertEqual(result['sql_type'], expected_type, f"Failed for: {sql}")

if __name__ == '__main__':
    unittest.main()

