"""
translation_merge 모듈 테스트
"""

import pytest
from translation_merge import (
    TranslationMerger, 
    JavaParser, 
    MethodTranslation, 
    ExtractedMethod,
    MergeResult,
)


class TestJavaParser:
    """JavaParser 클래스 테스트."""
    
    @pytest.fixture
    def parser(self):
        return JavaParser()
    
    def test_extract_imports_single(self, parser):
        """단일 import 추출 테스트."""
        code = "import java.util.List;"
        imports = parser.extract_imports(code)
        assert len(imports) == 1
        assert "import java.util.List;" in imports
    
    def test_extract_imports_multiple(self, parser):
        """다중 import 추출 테스트."""
        code = """
import java.util.List;
import java.util.ArrayList;
import java.io.File;
"""
        imports = parser.extract_imports(code)
        assert len(imports) == 3
    
    def test_extract_imports_static(self, parser):
        """static import 추출 테스트."""
        code = "import static java.lang.Math.PI;"
        imports = parser.extract_imports(code)
        assert len(imports) == 1
        assert "static" in imports[0]
    
    def test_extract_imports_wildcard(self, parser):
        """와일드카드 import 추출 테스트."""
        code = "import java.util.*;"
        imports = parser.extract_imports(code)
        assert len(imports) == 1
        assert "java.util.*" in imports[0]
    
    def test_extract_package_declaration(self, parser):
        """package 선언 추출 테스트."""
        code = """
package com.example.myapp;

import java.util.List;
"""
        pkg = parser.extract_package_declaration(code)
        assert pkg == "package com.example.myapp;"
    
    def test_extract_method_by_name_simple(self, parser):
        """간단한 메소드 추출 테스트."""
        code = """
public void processData() {
    int x = 1;
}
"""
        method = parser.extract_method_by_name(code, "processData")
        assert method is not None
        assert method.name == "processData"
        assert "public void processData()" in method.body
        assert "int x = 1;" in method.body
    
    def test_extract_method_by_name_with_nested_braces(self, parser):
        """중첩 중괄호가 있는 메소드 추출 테스트."""
        code = """
public void complexMethod() {
    if (true) {
        for (int i = 0; i < 10; i++) {
            System.out.println(i);
        }
    }
}
"""
        method = parser.extract_method_by_name(code, "complexMethod")
        assert method is not None
        assert method.body.count('{') == method.body.count('}')
    
    def test_extract_method_by_name_with_string_braces(self, parser):
        """문자열 내 중괄호가 있는 메소드 추출 테스트."""
        code = '''
public void stringMethod() {
    String s = "{ this is not a brace }";
    System.out.println(s);
}
'''
        method = parser.extract_method_by_name(code, "stringMethod")
        assert method is not None
        assert "System.out.println(s);" in method.body
    
    def test_extract_method_by_name_not_found(self, parser):
        """메소드를 찾지 못한 경우 테스트."""
        code = """
public void existingMethod() {
    int x = 1;
}
"""
        method = parser.extract_method_by_name(code, "nonExistentMethod")
        assert method is None
    
    def test_extract_method_with_parameters(self, parser):
        """파라미터가 있는 메소드 추출 테스트."""
        code = """
public String processWithParams(int id, String name, List<Data> items) {
    return name + id;
}
"""
        method = parser.extract_method_by_name(code, "processWithParams")
        assert method is not None
        assert "int id" in method.body
        assert "String name" in method.body
    
    def test_extract_method_with_throws(self, parser):
        """throws 절이 있는 메소드 추출 테스트."""
        code = """
public void riskyMethod() throws IOException, SQLException {
    throw new IOException();
}
"""
        method = parser.extract_method_by_name(code, "riskyMethod")
        assert method is not None
        assert "throws IOException, SQLException" in method.body
    
    def test_deduplicate_imports(self, parser):
        """import 중복 제거 테스트."""
        imports = [
            "import java.util.List;",
            "import java.util.ArrayList;",
            "import java.util.List;",  # 중복
            "import com.example.MyClass;",
        ]
        unique = parser.deduplicate_imports(imports)
        assert len(unique) == 3
        
    def test_deduplicate_imports_sorting(self, parser):
        """import 정렬 테스트 (java.* -> javax.* -> 기타)."""
        imports = [
            "import com.example.C;",
            "import javax.swing.JFrame;",
            "import java.util.List;",
        ]
        sorted_imports = parser.deduplicate_imports(imports)
        assert sorted_imports[0].startswith("import java.")
        assert sorted_imports[1].startswith("import javax.")
        assert sorted_imports[2].startswith("import com.")
    
    def test_extract_class_body_insertion_point(self, parser):
        """클래스 본문 삽입 위치 테스트."""
        skeleton = """
package com.example;

public class MyClass {
}
"""
        pos = parser.extract_class_body_insertion_point(skeleton)
        assert pos > 0
        assert skeleton[pos] == '}'


class TestTranslationMerger:
    """TranslationMerger 클래스 테스트."""
    
    @pytest.fixture
    def merger(self):
        # 기존 테스트는 플러그인 비활성화 상태로 실행
        return TranslationMerger(use_plugins=False)
    
    def test_merge_basic(self, merger):
        """기본 병합 테스트."""
        skeleton = """package com.example;

import java.util.List;

public class MyProgram {
}
"""
        translations = [
            MethodTranslation(
                name="processData",
                llm_response="""
import java.util.ArrayList;

public void processData() {
    List<String> data = new ArrayList<>();
}
"""
            ),
        ]
        
        result = merger.merge(skeleton, translations)
        
        assert isinstance(result, MergeResult)
        assert "processData" in result.methods
        assert "java.util.ArrayList" in result.imports or "ArrayList" in result.merged_code
        assert "public void processData()" in result.merged_code
    
    def test_merge_multiple_methods(self, merger):
        """다중 메소드 병합 테스트."""
        skeleton = """package com.example;

public class MyProgram {
}
"""
        translations = [
            MethodTranslation(
                name="method1",
                llm_response="""
public void method1() {
    int a = 1;
}
"""
            ),
            MethodTranslation(
                name="method2",
                llm_response="""
public void method2() {
    int b = 2;
}
"""
            ),
        ]
        
        result = merger.merge(skeleton, translations)
        
        assert len(result.methods) == 2
        assert "method1" in result.methods
        assert "method2" in result.methods
        assert "public void method1()" in result.merged_code
        assert "public void method2()" in result.merged_code
    
    def test_merge_with_warnings(self, merger):
        """메소드를 찾지 못한 경우 경고 테스트."""
        skeleton = """package com.example;

public class MyProgram {
}
"""
        translations = [
            MethodTranslation(
                name="nonExistent",
                llm_response="""
public void somethingElse() {
    int x = 1;
}
"""
            ),
        ]
        
        result = merger.merge(skeleton, translations)
        
        assert len(result.warnings) == 1
        assert "nonExistent" in result.warnings[0]
    
    def test_merge_import_deduplication(self, merger):
        """import 중복 제거 병합 테스트."""
        skeleton = """package com.example;

import java.util.List;

public class MyProgram {
}
"""
        translations = [
            MethodTranslation(
                name="method1",
                llm_response="""
import java.util.List;
import java.util.ArrayList;

public void method1() {
}
"""
            ),
            MethodTranslation(
                name="method2",
                llm_response="""
import java.util.ArrayList;

public void method2() {
}
"""
            ),
        ]
        
        result = merger.merge(skeleton, translations)
        
        # 중복된 import가 한 번만 나타나야 함
        import_count = result.merged_code.count("import java.util.ArrayList;")
        assert import_count == 1


class TestIntegration:
    """통합 테스트."""
    
    def test_full_merge_scenario(self):
        """전체 병합 시나리오 테스트."""
        merger = TranslationMerger()
        
        skeleton = """package com.example.app;

import java.util.List;

/**
 * Pro*C에서 변환된 메인 클래스
 */
public class MainProgram {
}
"""
        
        translations = [
            MethodTranslation(
                name="initialize",
                llm_response="""
import java.sql.Connection;
import java.sql.DriverManager;

/**
 * 초기화 메소드
 */
public void initialize() {
    Connection conn = null;
    try {
        conn = DriverManager.getConnection("jdbc:oracle:thin:@localhost:1521:xe");
    } catch (Exception e) {
        e.printStackTrace();
    }
}
"""
            ),
            MethodTranslation(
                name="processMain",
                llm_response="""
import java.util.ArrayList;
import java.util.Map;
import java.util.HashMap;

public void processMain() {
    List<String> items = new ArrayList<>();
    Map<String, Integer> counts = new HashMap<>();
    
    for (String item : items) {
        counts.put(item, counts.getOrDefault(item, 0) + 1);
    }
}
"""
            ),
        ]
        
        result = merger.merge(skeleton, translations)
        
        # 기본 검증
        assert "package com.example.app;" in result.merged_code
        assert len(result.methods) == 2
        assert "initialize" in result.methods
        assert "processMain" in result.methods
        
        # import 검증
        assert "java.sql.Connection" in result.merged_code
        assert "java.util.ArrayList" in result.merged_code
        
        # 메소드 본문 검증
        assert "DriverManager.getConnection" in result.merged_code
        assert "new HashMap<>()" in result.merged_code
        
        # 경고 없음
        assert len(result.warnings) == 0


class TestPluginSystem:
    """플러그인 시스템 테스트."""
    
    def test_list_plugins(self):
        """등록된 플러그인 목록 조회 테스트."""
        from translation_merge import list_plugins
        
        plugins = list_plugins()
        assert "bxmcategory" in plugins
        assert "main_deduplicator" in plugins
        assert "visibility" in plugins
    
    def test_load_plugins_priority_order(self):
        """플러그인이 priority 순서대로 로드되는지 테스트."""
        from translation_merge import load_plugins
        
        plugins = load_plugins()
        priorities = [p.priority for p in plugins]
        assert priorities == sorted(priorities)
    
    def test_bxmcategory_annotation_added(self):
        """@bxmcategory 어노테이션 추가 테스트."""
        merger = TranslationMerger()
        
        skeleton = """package com.example;

public class MyProgram {
}
"""
        translations = [
            MethodTranslation(
                name="processData",
                llm_response="""
public void processData() {
    int x = 1;
}
"""
            ),
        ]
        
        result = merger.merge(skeleton, translations)
        assert "@bxmcategory" in result.merged_code
    
    def test_bxmcategory_not_duplicated(self):
        """이미 @bxmcategory가 있으면 중복 추가 안됨 테스트."""
        merger = TranslationMerger()
        
        skeleton = """package com.example;

public class MyProgram {
}
"""
        translations = [
            MethodTranslation(
                name="processData",
                llm_response="""
@bxmcategory
public void processData() {
    int x = 1;
}
"""
            ),
        ]
        
        result = merger.merge(skeleton, translations)
        count = result.merged_code.count("@bxmcategory")
        assert count == 1
    
    def test_main_deduplicator_keeps_last(self):
        """중복 main 함수 중 마지막만 유지 테스트."""
        merger = TranslationMerger()
        
        skeleton = """package com.example;

public class MyProgram {
}
"""
        translations = [
            MethodTranslation(
                name="processMain",
                llm_response="""
public void processMain() {
    System.out.println("first main");
}
"""
            ),
            MethodTranslation(
                name="helperMethod",
                llm_response="""
public void helperMethod() {
    int x = 1;
}
"""
            ),
            MethodTranslation(
                name="runMain",
                llm_response="""
public void runMain() {
    System.out.println("second main");
}
"""
            ),
        ]
        
        result = merger.merge(skeleton, translations)
        
        # 첫 번째 main 함수는 제거됨
        assert "first main" not in result.merged_code
        # 마지막 main 함수만 유지
        assert "second main" in result.merged_code
        # helperMethod는 유지
        assert "helperMethod" in result.merged_code or "private void helperMethod" in result.merged_code
    
    def test_visibility_public_to_private(self):
        """public → private 변환 테스트 (main 제외)."""
        merger = TranslationMerger()
        
        skeleton = """package com.example;

public class MyProgram {
}
"""
        translations = [
            MethodTranslation(
                name="helperMethod",
                llm_response="""
public void helperMethod() {
    int x = 1;
}
"""
            ),
            MethodTranslation(
                name="processMain",
                llm_response="""
public void processMain() {
    System.out.println("main");
}
"""
            ),
        ]
        
        result = merger.merge(skeleton, translations)
        
        # helper는 private로 변환
        assert "private void helperMethod" in result.merged_code
        # main은 public 유지
        assert "public void processMain" in result.merged_code
    
    def test_plugins_disabled(self):
        """플러그인 비활성화 테스트."""
        merger = TranslationMerger(use_plugins=False)
        
        skeleton = """package com.example;

public class MyProgram {
}
"""
        translations = [
            MethodTranslation(
                name="helperMethod",
                llm_response="""
public void helperMethod() {
    int x = 1;
}
"""
            ),
        ]
        
        result = merger.merge(skeleton, translations)
        
        # 플러그인 비활성화 시 public 유지, 어노테이션 없음
        assert "public void helperMethod" in result.merged_code
        assert "@bxmcategory" not in result.merged_code
    
    def test_main_deduplicator_with_skeleton_main(self):
        """스켈레톤에 main 함수가 있는 경우 중복 제거 테스트."""
        merger = TranslationMerger()
        
        # 스켈레톤에 이미 main 메소드가 있음
        skeleton = """package com.example;

public class MyProgram {
    
    public void skeletonMain() {
        System.out.println("skeleton main");
    }
}
"""
        translations = [
            MethodTranslation(
                name="helperMethod",
                llm_response="""
public void helperMethod() {
    int x = 1;
}
"""
            ),
            MethodTranslation(
                name="newMain",
                llm_response="""
public void newMain() {
    System.out.println("new main from translation");
}
"""
            ),
        ]
        
        result = merger.merge(skeleton, translations)
        
        # 스켈레톤의 main 함수는 제거되고, 마지막 main (newMain)만 유지
        assert "skeleton main" not in result.merged_code
        assert "new main from translation" in result.merged_code
        # helperMethod는 유지
        assert "helperMethod" in result.merged_code


