"""Tái lập pipeline đã khóa trong môi trường đã cài; không tự đổi tham số."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def ensure_source(download=False):
    manifest = json.loads((ROOT/"datasets/manifest.json").read_text(encoding="utf-8"))
    path = ROOT/"datasets/ai4i/ai4i2020.csv"
    expected = next(e["sha256"] for e in manifest["files"] if e["path"] == "ai4i/ai4i2020.csv")
    if not path.exists():
        if not download:
            raise FileNotFoundError("Thiếu CSV AI4I. Tải theo datasets/README.md hoặc dùng --download.")
        with urllib.request.urlopen(manifest["sources"]["ai4i"]["download"], timeout=60) as response:
            payload = response.read()
        ziphash = next(e["sha256"] for e in manifest["files"] if e["path"] == "ai4i/ai4i2020.zip")
        if hashlib.sha256(payload).hexdigest() != ziphash:
            raise ValueError("ZIP nguồn khác phiên bản; không tiếp tục.")
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            content = archive.read("ai4i2020.csv")
        if hashlib.sha256(content).hexdigest() != expected:
            raise ValueError("CSV tải về sai checksum.")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError("CSV có sẵn sai checksum; không ghi đè dữ liệu nguồn.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--download", action="store_true", help="Tải AI4I chính thức nếu chưa có CSV.")
    args = parser.parse_args()
    ensure_source(args.download)
    (ROOT/".tmp").mkdir(exist_ok=True)
    for script in ("run_quality.py", "prepare_data.py", "create_splits.py", "train_isolation.py",
                   "train_classification.py", "evaluate_test.py", "build_handoff.py"):
        print("Running", script, flush=True)
        subprocess.run([sys.executable, str(ROOT/"scripts"/script)], cwd=ROOT, check=True)
    subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], cwd=ROOT, check=True)
    print("Reproduction complete; handoff-v1 is ready locally.")
