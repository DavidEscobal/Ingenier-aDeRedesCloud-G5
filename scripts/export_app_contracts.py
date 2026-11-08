"""Export OpenAPI from installed app packages; does not start servers."""
import json
from pathlib import Path

from g5_iam.main import app as iam
from g5_gateway.main import app as gateway
from g5_slice_manager.main import app as slice_manager

root = Path(__file__).resolve().parents[1] / "contracts" / "http"
root.mkdir(parents=True, exist_ok=True)
for name, app in (("gateway", gateway), ("slice-manager", slice_manager), ("iam", iam)):
    (root / f"{name}.openapi.json").write_text(
        json.dumps(app.openapi(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
