"""
Tree-sitter 라이브러리 임포트 및 초기화를 테스트하는 디버깅 스크립트입니다.
"""
print("Importing tree_sitter...")
import tree_sitter
print("Importing tree_sitter_c...")
import tree_sitter_c
print("Creating language...")
lang = tree_sitter.Language(tree_sitter_c.language())
print("Creating parser...")
parser = tree_sitter.Parser(lang)
print("Done.")
