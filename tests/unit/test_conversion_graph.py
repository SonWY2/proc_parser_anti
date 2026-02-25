from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from infra.agents.langchain.orchestration.conversion_graph import build_conversion_graph
from infra.agents.langchain.state import create_conversion_state


def test_conversion_graph_generates_artifacts(tmp_path, monkeypatch):
    monkeypatch.setenv("VLLM_MOCK", "true")

    header = tmp_path / "sample.h"
    header.write_text("typedef int INT_T;\n", encoding="utf-8")

    proc = tmp_path / "sample.pc"
    proc.write_text(
        """
int process_customer() {
    EXEC SQL SELECT CUST_ID INTO :cust_id FROM CUSTOMER WHERE ID = :id;
    return 0;
}
extern int external_call;
""".strip(),
        encoding="utf-8",
    )

    output_dir = tmp_path / "output"
    graph = build_conversion_graph()
    state = create_conversion_state(
        header_paths=[str(header)],
        proc_paths=[str(proc)],
        output_dir=str(output_dir),
        strategy="preserve",
    )

    result = graph.invoke(state)

    assert (output_dir / "java" / "service").exists()
    assert (output_dir / "mybatis" / "mapper").exists()
    assert (output_dir / "report" / "migration-report.md").exists()
    assert result.get("java_result", {}).get("mocked_vllm") is True
