"""
Pro*C 파서의 메인 진입점입니다.
커맨드 라인 인자를 처리하고 파싱 작업을 시작합니다.
"""
import argparse
import sys
from file_handler import process_directory

def main():
    parser = argparse.ArgumentParser(description='Pro*C Parser')
    parser.add_argument('input_dir', help='Input directory containing .pc and .h files')
    parser.add_argument('output_dir', help='Output directory for .jsonl files')
    
    args = parser.parse_args()
    
    try:
        process_directory(args.input_dir, args.output_dir)
        print("Processing completed successfully.")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
