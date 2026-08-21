from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.export_standalone_dashboard import export_dashboard


with tempfile.TemporaryDirectory() as directory:
    output = export_dashboard(Path(directory) / "dashboard.html")
    html = output.read_text(encoding="utf-8")
    assert "四配置 Brier 與權重凍結監控" in html
    assert "const SNAPSHOT=" in html
    assert "multiscale_calibrated" in html
print("Standalone dashboard export smoke checks passed.")
