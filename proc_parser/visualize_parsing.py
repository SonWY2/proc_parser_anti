"""
파싱 단계별 시각화 도구

각 파싱 단계가 진행될 때마다 추출된 요소들이 공백으로 대체되어
시각적으로 코드가 어떻게 "사라지는지" 보여줍니다.

각 단계마다 별도의 파일이 생성됩니다:
- stage_0_original.txt
- stage_1_after_include.txt
- stage_2_after_macro.txt
- stage_3_after_sql.txt
- stage_4_after_bamcall.txt
- stage_5_after_comments.txt
- stage_6_after_c_elements.txt
"""
import sys
import os
import re

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from proc_parser.patterns import (
    PATTERN_INCLUDE, PATTERN_MACRO, PATTERN_SQL,
    PATTERN_COMMENT_SINGLE, PATTERN_COMMENT_MULTI
)
from proc_parser.c_parser import CParser


def blank_region(content_list, start, end):
    """지정된 범위를 공백으로 대체 (줄바꿈 유지)"""
    for i in range(start, end):
        if i < len(content_list) and content_list[i] != '\n':
            content_list[i] = ' '


def save_stage(content_list, output_dir, stage_num, stage_name, original_content, extraction_history):
    """단계별 파일 저장"""
    filename = f"stage_{stage_num}_{stage_name}.c"
    filepath = os.path.join(output_dir, filename)
    
    content = "".join(content_list)
    remaining_chars = len([c for c in content if not c.isspace()])
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(f"/* {'='*60}\n")
        f.write(f" * PARSING STAGE {stage_num}: {stage_name.upper()}\n")
        f.write(f" * {'='*60}\n")
        f.write(f" * 남은 문자 수 (공백 제외): {remaining_chars}\n")
        f.write(f" *\n")
        f.write(f" * [추출 히스토리]\n")
        for i, (num, name, desc) in enumerate(extraction_history):
            marker = ">>>" if i == len(extraction_history) - 1 else "   "
            f.write(f" * {marker} Stage {num}: {desc}\n")
        f.write(f" * {'='*60}\n")
        f.write(f" */\n\n")
        f.write(content)
    
    print(f"  [Stage {stage_num}] {stage_name}: {filepath}")
    return filepath


def visualize_parsing_stages(file_path, output_dir=None):
    """파싱 단계별 시각화 실행 - 각 단계 파일 저장"""
    
    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        original_content = f.read()
    
    # 출력 디렉토리 설정
    if output_dir is None:
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        output_dir = os.path.join(os.path.dirname(file_path), f"{base_name}_parsing_stages")
    
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"\n파싱 파일: {file_path}")
    print(f"출력 디렉토리: {output_dir}")
    print(f"총 문자 수: {len(original_content)}")
    print(f"\n단계별 파일 생성 중...")
    
    content_list = list(original_content)
    saved_files = []
    extraction_history = []
    
    # Stage 0: 원본 저장
    extraction_history.append((0, "original", "원본 코드 (추출 없음)"))
    saved_files.append(save_stage(content_list, output_dir, 0, "original", original_content, extraction_history))
    
    # Stage 1: Include 추출
    for match in PATTERN_INCLUDE.finditer(original_content):
        blank_region(content_list, match.start(), match.end())
    extraction_history.append((1, "after_include", "#include 문 추출"))
    saved_files.append(save_stage(content_list, output_dir, 1, "after_include", original_content, extraction_history))
    
    # Stage 2: Macro 추출
    for match in PATTERN_MACRO.finditer(original_content):
        blank_region(content_list, match.start(), match.end())
    extraction_history.append((2, "after_macro", "#define 매크로 추출"))
    saved_files.append(save_stage(content_list, output_dir, 2, "after_macro", original_content, extraction_history))
    
    # Stage 3: SQL 블록 추출
    for match in PATTERN_SQL.finditer(original_content):
        blank_region(content_list, match.start(), match.end())
    extraction_history.append((3, "after_sql", "EXEC SQL 블록 추출"))
    saved_files.append(save_stage(content_list, output_dir, 3, "after_sql", original_content, extraction_history))
    
    # Stage 4: BAMCALL 추출
    bamcall_pattern = re.compile(r'BAMCALL\s*\([^)]+\)\s*;', re.MULTILINE)
    for match in bamcall_pattern.finditer(original_content):
        blank_region(content_list, match.start(), match.end())
    extraction_history.append((4, "after_bamcall", "BAMCALL 호출 추출"))
    saved_files.append(save_stage(content_list, output_dir, 4, "after_bamcall", original_content, extraction_history))
    
    # Stage 5: 주석 추출
    for match in PATTERN_COMMENT_SINGLE.finditer(original_content):
        blank_region(content_list, match.start(), match.end())
    for match in PATTERN_COMMENT_MULTI.finditer(original_content):
        blank_region(content_list, match.start(), match.end())
    extraction_history.append((5, "after_comments", "주석 (// 및 /* */) 추출"))
    saved_files.append(save_stage(content_list, output_dir, 5, "after_comments", original_content, extraction_history))
    
    # C 요소 파싱 (세부 단계로 분리)
    c_parser = CParser()
    c_source = "".join(content_list)
    c_elements = c_parser.parse(c_source)
    
    line_indices = [0]
    for i, char in enumerate(original_content):
        if char == '\n':
            line_indices.append(i + 1)
    
    def blank_element(el):
        start_line = el['line_start'] - 1
        end_line = el['line_end'] - 1
        if start_line < len(line_indices):
            s = line_indices[start_line]
            e = line_indices[end_line + 1] if end_line + 1 < len(line_indices) else len(original_content)
            blank_region(content_list, s, e)
    
    # Stage 6: 함수 호출 추출 (가장 내부 요소부터)
    func_calls = [el for el in c_elements if el['type'] == 'function_call']
    for el in func_calls:
        blank_element(el)
    extraction_history.append((6, "after_func_calls", f"함수 호출 추출 ({len(func_calls)}개)"))
    saved_files.append(save_stage(content_list, output_dir, 6, "after_func_calls", original_content, extraction_history))
    
    # Stage 7: 지역 변수 추출
    local_vars = [el for el in c_elements if el['type'] == 'variable' and el.get('function') is not None]
    for el in local_vars:
        blank_element(el)
    extraction_history.append((7, "after_local_vars", f"지역 변수 추출 ({len(local_vars)}개)"))
    saved_files.append(save_stage(content_list, output_dir, 7, "after_local_vars", original_content, extraction_history))
    
    # Stage 8: 함수 정의 추출 (함수 껍데기)
    functions = [el for el in c_elements if el['type'] == 'function']
    for el in functions:
        blank_element(el)
    extraction_history.append((8, "after_functions", f"함수 정의 추출 ({len(functions)}개)"))
    saved_files.append(save_stage(content_list, output_dir, 8, "after_functions", original_content, extraction_history))
    
    # Stage 9: 전역 변수 추출
    global_vars = [el for el in c_elements if el['type'] == 'variable' and el.get('function') is None]
    for el in global_vars:
        blank_element(el)
    extraction_history.append((9, "after_global_vars", f"전역 변수 추출 ({len(global_vars)}개)"))
    saved_files.append(save_stage(content_list, output_dir, 9, "after_global_vars", original_content, extraction_history))
    
    # Stage 10: 구조체 정의 추출
    structs = [el for el in c_elements if el['type'] == 'struct']
    for el in structs:
        blank_element(el)
    extraction_history.append((10, "after_structs", f"구조체 정의 추출 ({len(structs)}개)"))
    saved_files.append(save_stage(content_list, output_dir, 10, "after_structs", original_content, extraction_history))
    
    # 결과 요약
    remaining = "".join(content_list)
    remaining_chars = len([c for c in remaining if not c.isspace()])
    
    print(f"\n{'='*50}")
    print(f"[결과 요약]")
    print(f"  - 생성된 파일 수: {len(saved_files)}")
    print(f"  - 남은 문자 수 (공백 제외): {remaining_chars}")
    if remaining_chars > 0:
        print(f"  - 파싱되지 않은 영역이 존재합니다.")
    else:
        print(f"  - 모든 코드가 성공적으로 파싱되었습니다!")
    print(f"{'='*50}\n")
    
    return saved_files


if __name__ == "__main__":
    sample_file = os.path.join(project_root, 'tests', 'samples', 'sample.pc')
    sample_file = r"D:\workspace\proc_parser_antigravity\proc_parser\sample_input\original_source.sqc"
    # output_dir = os.path.dirname(sample_file) + ""
    # if len(sys.argv) > 1:
    #     sample_file = sys.argv[1]
    
    # if not os.path.exists(sample_file):
    #     print(f"파일을 찾을 수 없습니다: {sample_file}")
    #     sys.exit(1)
    
    output_dir = None
    if len(sys.argv) > 2:
        output_dir = sys.argv[2]
    
    visualize_parsing_stages(sample_file, output_dir)
