#!/usr/bin/env python3
"""
Pro*C → Java 멀티에이전트 변환 시스템 실행 스크립트

Usage:
    python run_multiagent_conversion.py \
        --headers include/types.h,include/customer.h \
        --procs src/customer.pc,src/order.pc \
        --output output/ \
        --knowledge docs/domain-rules.md
"""

import os
import sys
import argparse
import yaml
import json
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Any

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class MultiAgentOrchestrator:
    """멀티에이전트 변환 시스템 오케스트레이터"""
    
    def __init__(self, config_path: str = "config/multiagent_config.yaml"):
        """
        Args:
            config_path: 설정 파일 경로
        """
        self.config = self._load_config(config_path)
        self.start_time = None
        self.end_time = None
        
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """설정 파일 로드"""
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"설정 파일을 찾을 수 없습니다: {config_path}")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # 환경 변수 치환
        config = self._substitute_env_vars(config)
        return config
    
    def _substitute_env_vars(self, obj: Any) -> Any:
        """환경 변수 치환 (재귀)"""
        if isinstance(obj, dict):
            return {k: self._substitute_env_vars(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._substitute_env_vars(item) for item in obj]
        elif isinstance(obj, str) and obj.startswith('${') and obj.endswith('}'):
            env_var = obj[2:-1]
            return os.getenv(env_var, obj)
        return obj
    
    def run(
        self,
        header_paths: List[str],
        proc_paths: List[str],
        output_base_path: str,
        knowledge_doc_path: Optional[str] = None,
        strategy: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        멀티에이전트 변환 실행
        
        Args:
            header_paths: 헤더 파일 경로 리스트
            proc_paths: Pro*C 파일 경로 리스트
            output_base_path: 출력 기본 경로
            knowledge_doc_path: 지식 문서 경로 (선택)
            strategy: 변환 전략 (preserve | refactor), None이면 사용자에게 질문
        
        Returns:
            변환 결과 딕셔너리
        """
        self.start_time = datetime.now()
        print("=" * 80)
        print("Pro*C → Java 멀티에이전트 변환 시스템")
        print("=" * 80)
        print(f"시작 시간: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # 입력 검증
        self._validate_inputs(header_paths, proc_paths)
        
        # Step 1: 사용자 확인 (strategy가 None인 경우만)
        if strategy is None:
            strategy = self._ask_user_strategy()
        
        print(f"✅ 전략 결정: {strategy}")
        print()
        
        # Step 2: Analysis Agent 호출
        print("📊 Step 2: 코드 분석 중...")
        analysis_result = self._call_analysis_agent(
            header_paths, proc_paths, knowledge_doc_path, strategy
        )
        print(f"✅ 분석 완료: {len(analysis_result['files'])}개 파일, "
              f"{len(analysis_result['sql_blocks'])}개 SQL, "
              f"{len(analysis_result['extern_list'])}개 Extern")
        print()
        
        # Step 3: 병렬 변환 (Java + MyBatis)
        print("🔄 Step 3: 병렬 변환 중...")
        java_result, mybatis_result = self._parallel_conversion(
            analysis_result, strategy, output_base_path
        )
        print(f"✅ Java 생성: {java_result['total_classes']}개 클래스, "
              f"{java_result['total_stubs']}개 Stub")
        print(f"✅ MyBatis 생성: {mybatis_result['total_sqls']}개 SQL 변환")
        print()
        
        # Step 4: Report Agent 호출
        print("📝 Step 4: 리포트 생성 중...")
        report_path = self._call_report_agent(
            strategy, java_result, mybatis_result, 
            analysis_result['extern_list'], output_base_path
        )
        print(f"✅ 리포트 생성: {report_path}")
        print()
        
        # 완료
        self.end_time = datetime.now()
        duration = (self.end_time - self.start_time).total_seconds()
        
        result = {
            "status": "success",
            "strategy": strategy,
            "total_files_processed": len(header_paths) + len(proc_paths),
            "java_files_generated": java_result['total_classes'],
            "mybatis_files_generated": mybatis_result['total_sqls'],
            "report_path": report_path,
            "extern_stub_count": java_result['total_stubs'],
            "duration_seconds": duration
        }
        
        self._print_summary(result)
        return result
    
    def _validate_inputs(self, header_paths: List[str], proc_paths: List[str]):
        """입력 파일 검증"""
        print("🔍 입력 파일 검증 중...")
        
        all_paths = header_paths + proc_paths
        missing_files = [p for p in all_paths if not os.path.exists(p)]
        
        if missing_files:
            print("❌ 다음 파일을 찾을 수 없습니다:")
            for f in missing_files:
                print(f"   - {f}")
            raise FileNotFoundError("입력 파일이 존재하지 않습니다.")
        
        print(f"✅ 입력 파일 검증 완료: {len(all_paths)}개 파일")
    
    def _ask_user_strategy(self) -> str:
        """사용자에게 전략 질문"""
        print("=" * 80)
        print("코드 변환 전략 선택")
        print("=" * 80)
        print()
        print("코드 변환 시 '코드 리팩토링'을 포함하여 구조를 최적화할까요?")
        print("아니면 원본 코드의 구조를 최대한 유지할까요?")
        print()
        print("O: 리팩토링 포함 (OOP 원칙, Spring 표준 패턴, 클래스/메서드 재구성)")
        print("X: 구조 유지 (Pro*C 파일 1:1 Java 클래스, C 함수 1:1 메서드)")
        print()
        
        retry_count = 0
        while retry_count < 3:
            response = input("선택 (O/X): ").strip().upper()
            
            if response == "O":
                return "refactor"
            elif response == "X":
                return "preserve"
            else:
                print("⚠️  잘못된 입력입니다. O 또는 X를 입력하세요.")
                retry_count += 1
        
        raise ValueError("유효한 응답을 받지 못했습니다. 작업을 취소합니다.")
    
    def _call_analysis_agent(
        self,
        header_paths: List[str],
        proc_paths: List[str],
        knowledge_doc_path: Optional[str],
        strategy: str
    ) -> Dict[str, Any]:
        """Analysis Agent 호출 (시뮬레이션)"""
        
        # 실제 구현에서는 여기서 analysis-agent를 호출
        # 현재는 시뮬레이션으로 더미 데이터 반환
        
        print("   - 헤더 파일 분석 중...")
        print("   - Pro*C 파일 파싱 중...")
        print("   - SQL 추출 중...")
        print("   - Extern 참조 식별 중...")
        
        # 더미 결과
        return {
            "type_map": {
                "CHAR_100": "String",
                "INT_T": "int",
                "CUSTOMER": "CustomerDto"
            },
            "files": [
                {
                    "source_file": p,
                    "loc": 1000,
                    "chunked": False,
                    "functions": []
                }
                for p in proc_paths
            ],
            "sql_blocks": [],
            "extern_list": []
        }
    
    def _parallel_conversion(
        self,
        analysis_result: Dict[str, Any],
        strategy: str,
        output_base_path: str
    ) -> tuple:
        """병렬 변환 (Java + MyBatis)"""
        
        # 실제 구현에서는 여기서 병렬로 agent 호출
        # 현재는 순차 시뮬레이션
        
        print("   - Java Spring Agent 실행 중...")
        java_result = {
            "total_classes": len(analysis_result['files']),
            "total_stubs": len(analysis_result['extern_list']),
            "java_files": []
        }
        
        print("   - MyBatis Agent 실행 중...")
        mybatis_result = {
            "total_sqls": len(analysis_result['sql_blocks']),
            "dto_files": [],
            "dao_files": [],
            "xml_files": []
        }
        
        return java_result, mybatis_result
    
    def _call_report_agent(
        self,
        strategy: str,
        java_result: Dict[str, Any],
        mybatis_result: Dict[str, Any],
        extern_list: List[Dict],
        output_base_path: str
    ) -> str:
        """Report Agent 호출"""
        
        report_path = os.path.join(
            output_base_path,
            self.config['output']['report_path'],
            'migration-report.md'
        )
        
        # 디렉토리 생성
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        
        # 리포트 생성 (시뮬레이션)
        report_content = f"""# Migration Report

생성일: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
전략: {strategy}

## 1. 변환 요약

| 항목 | 수량 |
|------|------|
| 생성 Java 파일 | {java_result['total_classes']}개 |
| 생성 Stub 파일 | {java_result['total_stubs']}개 |
| 변환 SQL | {mybatis_result['total_sqls']}개 |

## 2. 검증 체크리스트

- [ ] 모든 EXEC SQL이 MyBatis XML로 추출되었는가
- [ ] Extern Stub이 실제 구현으로 교체되었는가
"""
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        return report_path
    
    def _print_summary(self, result: Dict[str, Any]):
        """완료 요약 출력"""
        print("=" * 80)
        print("✅ 변환 완료")
        print("=" * 80)
        print(f"전략: {result['strategy']}")
        print(f"처리 파일: {result['total_files_processed']}개")
        print(f"생성 Java 파일: {result['java_files_generated']}개")
        print(f"생성 MyBatis 파일: {result['mybatis_files_generated']}개")
        print(f"Extern Stub: {result['extern_stub_count']}개")
        print(f"처리 시간: {result['duration_seconds']:.1f}초")
        print()
        print(f"📄 리포트: {result['report_path']}")
        print("=" * 80)


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description="Pro*C → Java 멀티에이전트 변환 시스템",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--headers',
        required=True,
        help='헤더 파일 경로 (쉼표로 구분)'
    )
    
    parser.add_argument(
        '--procs',
        required=True,
        help='Pro*C 파일 경로 (쉼표로 구분)'
    )
    
    parser.add_argument(
        '--output',
        default='output/',
        help='출력 디렉토리 (기본값: output/)'
    )
    
    parser.add_argument(
        '--knowledge',
        help='지식 문서 경로 (선택)'
    )
    
    parser.add_argument(
        '--strategy',
        choices=['preserve', 'refactor'],
        help='변환 전략 (생략 시 사용자에게 질문)'
    )
    
    parser.add_argument(
        '--config',
        default='config/multiagent_config.yaml',
        help='설정 파일 경로'
    )
    
    args = parser.parse_args()
    
    # 파일 경로 파싱
    header_paths = [p.strip() for p in args.headers.split(',')]
    proc_paths = [p.strip() for p in args.procs.split(',')]
    
    try:
        # 오케스트레이터 초기화
        orchestrator = MultiAgentOrchestrator(config_path=args.config)
        
        # 변환 실행
        result = orchestrator.run(
            header_paths=header_paths,
            proc_paths=proc_paths,
            output_base_path=args.output,
            knowledge_doc_path=args.knowledge,
            strategy=args.strategy
        )
        
        # 결과 저장
        result_file = os.path.join(args.output, 'conversion_result.json')
        os.makedirs(os.path.dirname(result_file), exist_ok=True)
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        print(f"\n📊 결과 저장: {result_file}")
        sys.exit(0)
        
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
