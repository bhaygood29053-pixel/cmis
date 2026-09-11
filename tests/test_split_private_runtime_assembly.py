from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def test_public_source_can_import_private_split_package_module(tmp_path: Path) -> None:
    private_root = tmp_path / "private-wheel"
    private_cmis = private_root / "liquidity_scout" / "cmis"
    private_cmis.mkdir(parents=True)
    (private_cmis / "_private_overlay_probe.py").write_text(
        "VALUE = 'private-overlay-visible'\n",
        encoding="utf-8",
    )

    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join((str(ROOT), str(private_root)))
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import liquidity_scout.cmis._private_overlay_probe as probe; "
                "assert probe.VALUE == 'private-overlay-visible'; "
                "print(probe.VALUE)"
            ),
        ],
        cwd="/",
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "private-overlay-visible" in completed.stdout


def test_systemd_installer_overrides_legacy_versioned_execstart() -> None:
    script = (ROOT / "scripts" / "install_cmis_systemd.sh").read_text(encoding="utf-8")

    assert 'OVERRIDE_FILE="$OVERRIDE_DIR/zz-repository-runtime.conf"' in script
    assert "ExecStart=\nExecStart=$PYTHON -m liquidity_scout.cmis.http" in script
    assert "systemctl show -p ExecStart --value cmis-gateway.service" in script
    assert "systemctl show -p WorkingDirectory --value cmis-gateway.service" in script
    assert "Effective CMIS ExecStart is not using the repository virtualenv" in script
