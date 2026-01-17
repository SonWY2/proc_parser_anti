"""
CLI 인터페이스

서브에이전트 시스템을 커맨드라인에서 사용할 수 있게 합니다.
"""

import argparse
import json
from pathlib import Path
from typing import Optional

from .orchestrator import Orchestrator
from .llm_client import LLMConfig


def main():
    parser = argparse.ArgumentParser(
        description='서브에이전트 시스템 CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  # 에이전트 목록 확인
  python -m agent_system list
  
  # 특정 에이전트로 작업 실행
  python -m agent_system run proc-analyzer "main.py 파일의 SQL 패턴 분석"
  
  # 자동 매칭으로 작업 실행  
  python -m agent_system auto "Pro*C 코드에서 커서 찾기"
"""
    )
    
    subparsers = parser.add_subparsers(dest='command', help='명령어')
    
    # list 명령어
    list_parser = subparsers.add_parser('list', help='로드된 에이전트 목록')
    list_parser.add_argument('--path', type=str, help='에이전트 디렉토리 경로')
    
    # run 명령어
    run_parser = subparsers.add_parser('run', help='에이전트 실행')
    run_parser.add_argument('agent', type=str, help='에이전트 이름')
    run_parser.add_argument('task', type=str, help='수행할 작업')
    run_parser.add_argument('--path', type=str, help='에이전트 디렉토리 경로')
    run_parser.add_argument('--json', action='store_true', help='JSON 형식 출력')
    
    # auto 명령어
    auto_parser = subparsers.add_parser('auto', help='자동 매칭 실행')
    auto_parser.add_argument('request', type=str, help='사용자 요청')
    auto_parser.add_argument('--path', type=str, help='에이전트 디렉토리 경로')
    auto_parser.add_argument('--json', action='store_true', help='JSON 형식 출력')
    
    # tools 명령어
    tools_parser = subparsers.add_parser('tools', help='사용 가능한 도구 목록')
    
    args = parser.parse_args()
    
    if args.command is None:
        parser.print_help()
        return
    
    # 오케스트레이터 생성
    base_path = Path(args.path) if hasattr(args, 'path') and args.path else Path.cwd()
    orchestrator = Orchestrator()
    orchestrator.load_agents(base_path)
    
    if args.command == 'list':
        agents = orchestrator.list_agents()
        if not agents:
            print("로드된 에이전트가 없습니다.")
            print(f"에이전트 파일 위치: {base_path / '.agents'}")
            return
        
        print(f"\n📋 로드된 에이전트 ({len(agents)}개)\n")
        for agent in agents:
            print(f"  🤖 {agent['name']}")
            print(f"     설명: {agent['description'][:60]}...")
            print(f"     도구: {', '.join(agent['tools']) if agent['tools'] else '모든 도구'}")
            print(f"     모델: {agent['model']}")
            print()
    
    elif args.command == 'run':
        result = orchestrator.delegate(args.agent, args.task)
        
        if hasattr(args, 'json') and args.json:
            print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        else:
            print(f"\n{'='*60}")
            print(f"에이전트: {result.agent_name}")
            print(f"성공: {'✅' if result.success else '❌'}")
            print(f"실행 시간: {result.execution_time:.2f}초")
            print(f"도구 호출: {len(result.tool_calls)}회")
            print(f"{'='*60}\n")
            
            if result.error:
                print(f"❌ 에러: {result.error}\n")
            else:
                print(result.output)
    
    elif args.command == 'auto':
        result = orchestrator.auto_delegate(args.request)
        
        if result is None:
            print("매칭되는 에이전트가 없습니다.")
            return
        
        if hasattr(args, 'json') and args.json:
            print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        else:
            print(f"\n🤖 자동 선택된 에이전트: {result.agent_name}\n")
            print(f"{'='*60}")
            if result.error:
                print(f"❌ 에러: {result.error}")
            else:
                print(result.output)
            print(f"{'='*60}")
    
    elif args.command == 'tools':
        tools = orchestrator.available_tools
        print(f"\n🔧 사용 가능한 도구 ({len(tools)}개)\n")
        for tool in tools:
            print(f"  - {tool}")


if __name__ == '__main__':
    main()
