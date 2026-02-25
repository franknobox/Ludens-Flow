import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

try:
    from test_step4_acceptance import run_flow_test
    run_flow_test()
except Exception as e:
    with open("error_trace.txt", "w", encoding="utf-8") as f:
        f.write(traceback.format_exc())
