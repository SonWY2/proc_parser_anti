"""
네이밍 컨벤션 플러그인 테스트 모듈입니다.
SnakeToCamelPlugin의 변환 로직을 검증합니다.
"""
import unittest
from plugins.naming_convention import SnakeToCamelPlugin

class TestSnakeToCamelPlugin(unittest.TestCase):
    def setUp(self):
        self.plugin = SnakeToCamelPlugin()

    def test_simple_snake_case(self):
        self.assertEqual(self.plugin.convert("user_id"), "userId")
        self.assertEqual(self.plugin.convert("my_variable_name"), "myVariableName")

    def test_single_word(self):
        self.assertEqual(self.plugin.convert("variable"), "variable")

    def test_with_colon(self):
        self.assertEqual(self.plugin.convert(":user_id"), "userId")

    def test_already_camel(self):
        self.assertEqual(self.plugin.convert("userId"), "userId")
        # Note: SnakeToCamel assumes input is snake_case. 
        # If input is camelCase, it treats it as single word if no underscores.
        
    def test_mixed_case(self):
        # "User_Id" -> "UserId"
        self.assertEqual(self.plugin.convert("User_Id"), "UserId")

if __name__ == '__main__':
    unittest.main()
