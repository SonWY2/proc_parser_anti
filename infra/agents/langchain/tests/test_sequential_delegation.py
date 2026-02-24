"""
순차적 테스트: Orchestrator → Parser Agent 위임 검증 (Workspace 버전)

1) 메인 오케스트레이션이 작업 할당
2) Parser Agent에 작업 위임
3) Parser Agent가 parsing 모듈 skills로 메타데이터 추출
4) 결과를 Workspace에 저장하고 메시지 교환 기록

실행:
    python infra/agents/langchain/tests/test_sequential_delegation.py
    python infra/agents/langchain/tests/test_sequential_delegation.py --workspace ./my_workspace
"""

import argparse
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

# 프로젝트 루트 경로 추가 (parsing 모듈 import 위해)
PROJECT_ROOT = Path(__file__).resolve().parents[4]  # proc_parser 폴더
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# AgentWorkspace 경로 추가
LANGCHAIN_DIR = Path(__file__).resolve().parents[1]
if str(LANGCHAIN_DIR) not in sys.path:
    sys.path.insert(0, str(LANGCHAIN_DIR))

from workspace import AgentWorkspace

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)


def test_orchestrator_to_parser(workspace_dir: str = "./agent_workspace"):
    """
    테스트: Orchestrator → Parser Agent 위임
    
    Args:
        workspace_dir: 워크스페이스 디렉토리 경로
    """
    # Workspace 초기화
    workspace = AgentWorkspace(workspace_dir)
    print(f"\n📂 Workspace: {workspace.workspace_dir.absolute()}")
    
    # ========================================
    # 1) 메인 오케스트레이션이 작업 할당받음
    # ========================================
    workspace.send_message(
        from_agent="System",
        to_agent="Orchestrator",
        message_type="request",
        content={
            "task": "Pro*C 파일 분석 및 메타데이터 추출",
            "filename": "order.pc"
        }
    )
    
    # 테스트용 Pro*C 코드
    test_code = '''
/* order.pc - 주문 처리 Pro*C */
EXEC SQL INCLUDE sqlca;
EXEC SQL INCLUDE "order_types.h";

#define MAX_ORDERS 100
#define STATUS_ACTIVE 1

/* 헤더 종속성 예시 */
#include <stdio.h>
#include <string.h>

struct order_info {
    int order_id;
    char customer_name[50];
    double total_amount;
    int status;
};

/* 전역 호스트 변수 */
EXEC SQL BEGIN DECLARE SECTION;
    int g_order_count;
    char g_last_error[256];
EXEC SQL END DECLARE SECTION;

/* 함수: 주문 조회 */
int get_order_count(int customer_id) {
    EXEC SQL BEGIN DECLARE SECTION;
        int v_count = 0;
    EXEC SQL END DECLARE SECTION;
    
    EXEC SQL SELECT COUNT(*) INTO :v_count 
             FROM orders 
             WHERE customer_id = :customer_id 
               AND status = :STATUS_ACTIVE;
    
    return v_count;
}

/* 함수: 주문 업데이트 */
int update_order_status(int order_id, int new_status) {
    EXEC SQL UPDATE orders
             SET status = :new_status,
                 updated_at = SYSDATE
             WHERE order_id = :order_id;
    
    if (sqlca.sqlcode != 0) {
        strcpy(g_last_error, sqlca.sqlerrm.sqlerrmc);
        return -1;
    }
    
    EXEC SQL COMMIT;
    return 0;
}
'''
    
    # 소스 파일을 Workspace에 저장
    source_path = workspace.save_source("order.pc", test_code)
    
    # ========================================
    # 2) Orchestrator → Parser Agent 위임
    # ========================================
    workspace.send_message(
        from_agent="Orchestrator",
        to_agent="Parser",
        message_type="request",
        content={
            "action": "parse_and_extract_metadata",
            "source_file": "order.pc"
        },
        file_refs=[str(source_path)]
    )
    
    # ========================================
    # 3) Parser Agent가 Skill 사용하여 분석
    # ========================================
    workspace.send_message(
        from_agent="Parser",
        to_agent="Skill:parse_proc_code",
        message_type="request",
        content={"file": "order.pc"}
    )
    
    try:
        from parsing.core import ProCParser
        
        parser = ProCParser()
        
        # 임시 파일로 저장하여 파싱
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.pc', delete=False, encoding='utf-8') as f:
            f.write(test_code)
            temp_path = f.name
        
        # 파싱 실행
        elements = parser.parse_file(temp_path)
        
        # 임시 파일 삭제
        Path(temp_path).unlink()
        
        workspace.send_message(
            from_agent="Skill:parse_proc_code",
            to_agent="Parser",
            message_type="response",
            content={
                "status": "success",
                "total_elements": len(elements)
            }
        )
        
    except Exception as e:
        workspace.send_message(
            from_agent="Skill:parse_proc_code",
            to_agent="Parser",
            message_type="error",
            content={"error": str(e)}
        )
        workspace.print_message_history()
        logger.error(f"파싱 실패: {e}")
        return False
    
    # ========================================
    # 4) 메타데이터 분류 및 저장
    # ========================================
    metadata = {
        "headers": [],
        "includes": [],
        "macros": [],
        "host_vars": [],
        "sql_blocks": [],
        "functions": [],
        "structs": [],
        "others": []
    }
    
    for elem in elements:
        etype = elem.get("type", "unknown")
        
        if etype == "include":
            if "EXEC SQL" in str(elem.get("raw", "")):
                metadata["headers"].append(elem)
            else:
                metadata["includes"].append(elem)
        elif etype == "macro":
            metadata["macros"].append(elem)
        elif etype == "sql":
            metadata["sql_blocks"].append(elem)
        elif etype == "function":
            metadata["functions"].append(elem)
        elif etype == "struct":
            metadata["structs"].append(elem)
        elif etype == "variable":
            metadata["host_vars"].append(elem)
        else:
            metadata["others"].append(elem)
    
    # 메타데이터를 Workspace에 저장
    metadata_path = workspace.save_data("metadata", metadata, from_agent="Parser")
    
    # 요약 정보 저장
    summary = {
        "filename": "order.pc",
        "counts": {k: len(v) for k, v in metadata.items()},
        "timestamp": datetime.now().isoformat()
    }
    summary_path = workspace.save_data("metadata_summary", summary, from_agent="Parser")
    
    # ========================================
    # 5) Parser → Orchestrator 결과 반환
    # ========================================
    workspace.send_message(
        from_agent="Parser",
        to_agent="Orchestrator",
        message_type="response",
        content={
            "status": "success",
            "summary": summary["counts"]
        },
        file_refs=[str(metadata_path), str(summary_path)]
    )
    
    workspace.send_message(
        from_agent="Orchestrator",
        to_agent="System",
        message_type="response",
        content={
            "status": "complete",
            "result": "metadata extracted"
        }
    )
    
    # ========================================
    # 결과 출력
    # ========================================
    workspace.print_message_history()
    
    print("\n📊 Workspace 요약:")
    ws_summary = workspace.get_summary()
    print(f"  📁 경로: {ws_summary['path']}")
    print(f"  📄 데이터 파일: {ws_summary['data_files']}")
    print(f"  📦 아티팩트: {ws_summary['artifacts']}")
    print(f"  💬 총 메시지: {ws_summary['total_messages']}개")
    
    print("\n� 추출된 메타데이터:")
    print("-" * 40)
    for key, items in metadata.items():
        if items:
            print(f"  {key}: {len(items)}개")
    
    # 대화 로그 내보내기
    log_path = workspace.export_conversation()
    print(f"\n📝 대화 로그 저장됨: {log_path}")
    
    print("\n✅ 테스트 완료!")
    return True


def main():
    parser = argparse.ArgumentParser(description="Orchestrator → Parser 위임 테스트")
    parser.add_argument(
        "--workspace", "-w",
        default="./agent_workspace",
        help="워크스페이스 디렉토리 경로 (기본: ./agent_workspace)"
    )
    parser.add_argument(
        "--clean", "-c",
        action="store_true",
        help="테스트 전 워크스페이스 초기화"
    )
    
    args = parser.parse_args()
    
    if args.clean:
        ws = AgentWorkspace(args.workspace)
        ws.clear()
        print(f"🗑️ 워크스페이스 초기화됨: {args.workspace}")
    
    success = test_orchestrator_to_parser(args.workspace)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
