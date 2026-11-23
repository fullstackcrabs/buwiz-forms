"""Keep the desktop release tag and the packaged NSH version in sync."""

import argparse
import json
import re
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version")
    args = parser.parse_args()
    if not re.fullmatch(r"(?:0|[1-9][0-9]{0,2})\.(?:0|[1-9][0-9]{0,2})\.(?:0|[1-9][0-9]{0,4})", args.version):
        parser.error("expected a desktop release version in MAJOR.MINOR.PATCH format")
    if any(int(part) > limit for part, limit in zip(args.version.split("."), (255, 255, 65535))):
        parser.error("desktop release version exceeds MSI limits (255.255.65535)")

    path = Path(__file__).resolve().parents[1] / "nsh/nsh.json"
    config = json.loads(path.read_text(encoding="utf-8"))
    if config["version"] != args.version:
        config["version"] = args.version
        path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
