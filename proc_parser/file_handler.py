"""
파일 및 디렉토리 처리를 담당하는 모듈입니다.
입력 디렉토리를 순회하며 파일을 파싱하고 결과를 출력 디렉토리에 저장합니다.
"""
import os
import json
from .core import ProCParser

def process_directory(input_dir, output_dir):
    """
    입력 디렉토리를 순회하며 .pc 및 .h 파일을 파싱하고 결과를 출력 디렉토리에 씁니다.
    결과는 요소 유형별로 분리되어 저장됩니다 (예: sql.jsonl, function.jsonl).
    """
    parser = ProCParser()
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    # 이번 실행에서 열었던 파일을 추적하여 먼저 자르기 위해 세트를 사용합니다.
    initialized_files = set()

    for root, dirs, files in os.walk(input_dir):
        for file in files:
            if file.endswith(('.pc', '.h')):
                file_path = os.path.join(root, file)
                print(f"Processing {file_path}...")
                
                try:
                    elements = parser.parse_file(file_path)
                    
                    # 타입별 그룹화
                    elements_by_type = {}
                    for el in elements:
                        el_type = el.get('type', 'unknown')
                        if el_type not in elements_by_type:
                            elements_by_type[el_type] = []
                        elements_by_type[el_type].append(el)
                    
                    # 타입별 파일에 쓰기
                    for el_type, items in elements_by_type.items():
                        output_filename = f"{el_type}.jsonl"
                        output_file_path = os.path.join(output_dir, output_filename)
                        
                        mode = 'a'
                        if output_filename not in initialized_files:
                            mode = 'w' # 이번 실행의 첫 번째 쓰기에서 덮어쓰기
                            initialized_files.add(output_filename)
                            
                        with open(output_file_path, mode, encoding='utf-8') as f:
                            for item in items:
                                f.write(json.dumps(item, ensure_ascii=False) + '\n')
                                
                except Exception as e:
                    print(f"Failed to process {file_path}: {e}")
