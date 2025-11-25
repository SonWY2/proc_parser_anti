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

if __name__ == '__main__':
    unittest.main()
