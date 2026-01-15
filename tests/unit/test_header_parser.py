"""
header_parser 모듈 테스트
"""
import pytest
import os
import sys

# 상위 디렉토리를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from header_parser import TypedefStructParser, STPParser, HeaderParser
from shared_config import snake_to_camel, find_count_field


class TestSnakeToCamel:
    """snake_to_camel 함수 테스트"""
    
    def test_basic_conversion(self):
        assert snake_to_camel("user_name") == "userName"
        assert snake_to_camel("rfrn_strt_date") == "rfrnStrtDate"
        
    def test_single_word(self):
        assert snake_to_camel("name") == "name"
        
    def test_already_camel(self):
        # snake_to_camel은 첫 컴포넌트를 소문자로 변환
        assert snake_to_camel("userName") == "username"
        
    def test_leading_underscore(self):
        # 언더스코어로 시작하는 경우
        result = snake_to_camel("a_nxt_sqno")
        assert result == "aNxtSqno"


class TestTypedefStructParser:
    """TypedefStructParser 테스트"""
    
    @pytest.fixture
    def parser(self):
        return TypedefStructParser()
    
    @pytest.fixture
    def sample_header(self):
        return '''
typedef struct {
    char rfrn_strt_date [8 + 1];  //조회시작일자
    char rfrn_end_date [8 + 1];   //조회종료일자
    long a_nxt_sqno;              //다음일련번호
} spaa010p_inrec1;

typedef struct {
    spaa010p_inrec1 inrec1;       //InRec1
} spaa010p_in_t;
'''
    
    def test_parse_struct(self, parser, sample_header):
        result = parser.parse(sample_header)
        
        assert "spaa010p_inrec1" in result
        assert "spaa010p_in_t" in result
        
    def test_parse_fields(self, parser, sample_header):
        result = parser.parse(sample_header)
        struct = result["spaa010p_inrec1"]
        
        assert len(struct.fields) == 3
        
        # 첫 번째 필드
        field0 = struct.fields[0]
        assert field0.name == "rfrn_strt_date"
        assert field0.data_type == "char"
        assert field0.array_size == "8 + 1"
        assert field0.comment == "조회시작일자"
        
    def test_parse_nested_struct(self, parser, sample_header):
        result = parser.parse(sample_header)
        struct = result["spaa010p_in_t"]
        
        assert len(struct.fields) == 1
        assert struct.fields[0].name == "inrec1"
        assert struct.fields[0].data_type == "spaa010p_inrec1"


class TestSTPParser:
    """STPParser 테스트"""
    
    @pytest.fixture
    def parser(self):
        return STPParser()
    
    @pytest.fixture
    def sample_stp(self):
        return '''
int spaa010p_in_stp[] =
{
    'w',     12,      1,     sizeof(spaa010p_inrec1),
    's',      8,      9,      8,
    's',      8,      9,      8,
    'l',     11,      0,     10,
    '0',      0,      0,      0
};
'''
    
    def test_parse_stp(self, parser, sample_stp):
        result = parser.parse(sample_stp)
        
        assert "spaa010p_in_stp" in result
        items = result["spaa010p_in_stp"]
        
        # 'w' 타입은 STP_PATTERN에 sizeof가 포함되어 매칭 안됨
        assert len(items) == 4
        assert items[0][0] == 's'  # string
        assert items[1][0] == 's'  # string
        assert items[2][0] == 'l'  # long
        
    def test_get_struct_name(self, parser):
        assert parser.get_struct_name("spaa010p_in_stp") == "spaa010p_in_t"


class TestFindCountField:
    """find_count_field 함수 테스트"""
    
    def test_count_pattern(self):
        fields = {"outrec1_count", "outrec1", "other_field"}
        result = find_count_field("outrec1", fields)
        assert result == "outrec1Count"
        
    def test_cnt_pattern(self):
        fields = {"outrec1_cnt", "outrec1", "other_field"}
        result = find_count_field("outrec1", fields)
        assert result == "outrec1Cnt"
        
    def test_no_match(self):
        fields = {"outrec1", "other_field", "total_count"}
        result = find_count_field("outrec1", fields)
        assert result is None
        
    def test_manual_mapping(self):
        fields = {"total_items", "outrec1"}
        manual = {"outrec1": "total_items"}
        result = find_count_field("outrec1", fields, manual)
        assert result == "totalItems"


class TestHeaderParser:
    """HeaderParser 통합 테스트"""
    
    @pytest.fixture
    def parser(self):
        return HeaderParser(external_macros={"MAX_SIZE": 30})
    
    def test_parse_sample_h(self, parser):
        """sample.h 파일 파싱 테스트"""
        sample_path = os.path.join(
            os.path.dirname(__file__), 
            "..", "sample_input", "sample.h"
        )
        
        if not os.path.exists(sample_path):
            pytest.skip("sample.h not found")
        
        result = parser.parse_file(sample_path)
        
        # 구조체가 파싱되었는지 확인
        assert len(result) > 0
        
        # 적어도 하나의 in/out 구조체가 있어야 함
        struct_names = list(result.keys())
        assert any("inrec" in name or "outrec" in name for name in struct_names)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
