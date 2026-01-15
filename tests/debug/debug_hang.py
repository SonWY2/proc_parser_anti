"""
파서가 멈추는지 확인하기 위한 디버깅 스크립트입니다.
간단한 파일을 생성하고 파싱하여 프로세스가 완료되는지 확인합니다.
"""
from parser_core import ProCParser
import sys

print("Starting parser...")
parser = ProCParser()
print("Parser initialized.")
content = "void main() {}"
with open("debug_temp.pc", "w") as f:
    f.write(content)
print("File written.")
elements = parser.parse_file("debug_temp.pc")
print(f"Parsed {len(elements)} elements.")
