"""Install genuine BDG2 model artifacts from a distributed ZIP.

Usage:
    python scripts/install_artifacts.py path/to/fluxora_artifacts.zip

The script refuses to install anything whose SHA-256 does not match the
checksums pinned by the real-artifact integration tests, so a corrupted or
wrong export can never silently replace the genuine files.

Exit codes:
    0  success
    2  usage / missing members in the ZIP
    3  checksum or content validation failure
    4  destination already has artifacts (use --force to overwrite)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]

# Keep in sync with app/tests/test_real_artifacts_integration.py — the
# integration tests pin these exact checksums of the genuine Colab export.
EXPECTED_ANOMALY_SHA256 = (
    "7dd68ffe830aaa9d83075c0fc61e567ba2507e1972897380aee2844efedc8f7f"
)
EXPECTED_FORECAST_SHA256 = (
    "00e6bfe3d3d046b70f66ef3c18c5d0bf62d1b0d69c0ce1eee55af1ea7e7abc29"
)

REQUIRED_MEMBERS = (
    "anomaly_model.joblib",
    "forecast_model.joblib",
    "model_config.json",
    "forecast_metrics.json",
)


def expected_checksums() -> dict[str, str]:
    """Pinned checksums, resolved at call time (module constants stay patchable)."""
    return {
        "anomaly_model.joblib": EXPECTED_ANOMALY_SHA256,
        "forecast_model.joblib": EXPECTED_FORECAST_SHA256,
    }


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def install(zip_path: Path, dest: Path, force: bool = False) -> int:
    if not zip_path.is_file():
        print(f"ERROR: ZIP not found: {zip_path}", file=sys.stderr)
        return 2

    try:
        archive = zipfile.ZipFile(zip_path)
    except zipfile.BadZipFile:
        print(f"ERROR: not a valid ZIP archive: {zip_path}", file=sys.stderr)
        return 2

    with archive:
        names = set(archive.namelist())
        # Members may sit at the archive root or in a single top folder.
        prefix = ""
        missing = list(REQUIRED_MEMBERS)
        for candidate in ("", "artifacts/", "fluxora_artifacts/"):
            if all(candidate + member in names for member in REQUIRED_MEMBERS):
                prefix = candidate
                missing = []
                break
        if missing:
            print(
                "ERROR: ZIP is missing required members: " + ", ".join(missing),
                file=sys.stderr,
            )
            return 2

        with tempfile.TemporaryDirectory() as tmp:
            staging = Path(tmp)
            for member in REQUIRED_MEMBERS:
                with archive.open(prefix + member) as src, (staging / member).open(
                    "wb"
                ) as dst:
                    shutil.copyfileobj(src, dst)

            for member, expected in expected_checksums().items():
                actual = sha256_of(staging / member)
                if actual != expected:
                    print(
                        f"ERROR: checksum mismatch for {member}\n"
                        f"  expected sha256 {expected}\n"
                        f"  actual   sha256 {actual}\n"
                        "The file is corrupted or is not the genuine Colab export.",
                        file=sys.stderr,
                    )
                    return 3

            for member in ("model_config.json", "forecast_metrics.json"):
                try:
                    json.loads((staging / member).read_text(encoding="utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                    print(
                        f"ERROR: {member} is not valid JSON: {exc}", file=sys.stderr
                    )
                    return 3

            dest.mkdir(parents=True, exist_ok=True)
            existing = [m for m in REQUIRED_MEMBERS if (dest / m).exists()]
            if existing and not force:
                print(
                    "ERROR: destination already contains: "
                    + ", ".join(existing)
                    + f"\n  Re-run with --force to overwrite {dest}.",
                    file=sys.stderr,
                )
                return 4

            for member in REQUIRED_MEMBERS:
                shutil.copy2(staging / member, dest / member)

    print(f"OK: installed {len(REQUIRED_MEMBERS)} artifact files into {dest}")
    for member in REQUIRED_MEMBERS:
        digest = sha256_of(dest / member)
        print(f"  {digest[:16]}…  {member}")
    print("Run `pytest app/tests -q` — the real-artifact tests should now run.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("zip", type=Path, help="path to the artifacts ZIP")
    parser.add_argument(
        "--dest",
        type=Path,
        default=BACKEND_ROOT / "artifacts",
        help="destination directory (default: backend/artifacts)",
    )
    parser.add_argument(
        "--force", action="store_true", help="overwrite existing artifact files"
    )
    args = parser.parse_args(argv)
    return install(args.zip.resolve(), args.dest.resolve(), force=args.force)


if __name__ == "__main__":
    raise SystemExit(main())
