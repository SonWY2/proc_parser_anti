"""
기본적인 파일 쓰기 및 출력을 테스트하는 디버깅 스크립트입니다.
"""
with open("debug_output.txt", "w") as f:
    f.write("Hello from python")
print("Printed to stdout")
