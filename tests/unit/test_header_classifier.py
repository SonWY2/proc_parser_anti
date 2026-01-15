"""
header_parser 모듈 테스트 - 헤더 분류 및 매크로 추출
"""
import pytest
import os
import sys

# 상위 디렉토리를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from header_parser import (
    HeaderClassifier, HeaderType, HeaderInfo,
    MacroExtractor,
    IntegratedHeaderParser, ParseResult,
)


class TestHeaderClassifier:
    """HeaderClassifier 테스트"""
    
    @pytest.fixture
    def classifier(self):
        return HeaderClassifier()
    
    def test_classify_stp_header(self, classifier):
        """STP 헤더 분류"""
        content = '''
typedef struct {
    char name[20];
    int age;
} user_info_t;

int user_info_stp[] = {
    's', 20, 0, 0,
    'i', 10, 0, 0,
    '0', 0, 0, 0
};
'''
        info = classifier.classify(content, "test.h")
        assert info.header_type == HeaderType.STP_HEADER
        assert info.has_stp == True
        assert info.has_typedef == True
    
    def test_classify_struct_header(self, classifier):
        """구조체 헤더 분류"""
        content = '''
typedef struct {
    int id;
    char name[50];
} simple_struct;
'''
        info = classifier.classify(content, "test.h")
        assert info.header_type == HeaderType.STRUCT_HEADER
        assert info.has_typedef == True
        assert info.has_stp == False
    
    def test_classify_macro_header(self, classifier):
        """매크로 헤더 분류"""
        content = '''
#define MAX_SIZE 100
#define BUFFER_LEN 256
#define VERSION "1.0.0"
'''
        info = classifier.classify(content, "test.h")
        assert info.header_type == HeaderType.MACRO_HEADER
        assert info.has_macros == True
        assert info.macro_count == 3
    
    def test_classify_function_header(self, classifier):
        """함수 선언 헤더 분류"""
        content = '''
extern int initialize_db(void);
int process_data(char *input, int size);
void cleanup(void);
'''
        info = classifier.classify(content, "test.h")
        assert info.header_type == HeaderType.FUNCTION_HEADER
        assert info.has_functions == True
    
    def test_classify_mixed_header(self, classifier):
        """혼합 헤더 분류"""
        content = '''
#define MAX_SIZE 100

typedef struct {
    int value;
} data_t;
'''
        info = classifier.classify(content, "test.h")
        assert info.header_type == HeaderType.MIXED_HEADER


class TestMacroExtractor:
    """MacroExtractor 테스트"""
    
    @pytest.fixture
    def extractor(self):
        return MacroExtractor()
    
    def test_extract_numeric_macros(self, extractor):
        """숫자 매크로 추출"""
        content = '''
#define MAX_SIZE 100
#define BUFFER_LEN 256
#define SMALL_SIZE 8
'''
        macros = extractor.extract(content)
        assert macros["MAX_SIZE"] == 100
        assert macros["BUFFER_LEN"] == 256
        assert macros["SMALL_SIZE"] == 8
    
    def test_extract_hex_macros(self, extractor):
        """16진수 매크로 추출"""
        content = '''
#define FLAG_A 0x01
#define FLAG_B 0xFF
'''
        macros = extractor.extract(content)
        assert macros["FLAG_A"] == 1
        assert macros["FLAG_B"] == 255
    
    def test_extract_string_macros(self, extractor):
        """문자열 매크로 추출"""
        content = '''
#define VERSION "1.0.0"
#define APP_NAME "MyApp"
'''
        macros = extractor.extract(content)
        assert macros["VERSION"] == "1.0.0"
        assert macros["APP_NAME"] == "MyApp"
    
    def test_extract_expression_macros(self, extractor):
        """수식 매크로 추출"""
        content = '''
#define BASE 8
#define SIZE 9
'''
        macros = extractor.extract(content)
        assert macros["BASE"] == 8
        assert macros["SIZE"] == 9
    
    def test_get_numeric_macros(self, extractor):
        """숫자 매크로만 필터링"""
        content = '''
#define SIZE 100
#define NAME "test"
#define FLAG 0x01
'''
        all_macros = extractor.extract(content)
        numeric = extractor.get_numeric_macros(all_macros)
        
        assert "SIZE" in numeric
        assert "FLAG" in numeric
        assert "NAME" not in numeric


class TestIntegratedHeaderParser:
    """IntegratedHeaderParser 테스트"""
    
    @pytest.fixture
    def parser(self):
        return IntegratedHeaderParser(verbose=False)
    
    def test_parse_headers_list(self, parser):
        """헤더 목록 직접 파싱"""
        sample_h = os.path.join(
            os.path.dirname(__file__),
            "..", "sample_input", "sample.h"
        )
        
        if not os.path.exists(sample_h):
            pytest.skip("sample.h not found")
        
        result = parser.parse_headers([sample_h])
        
        assert result.total_headers == 1
        assert len(result.stp_headers) > 0 or len(result.struct_headers) > 0
    
    def test_parse_result_structure(self, parser):
        """ParseResult 구조 검증"""
        result = ParseResult()
        result.source_file = "test.pc"
        result.macros = {"MAX": 100}
        
        result_dict = result.to_dict()
        assert "source_file" in result_dict
        assert "macros" in result_dict


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
