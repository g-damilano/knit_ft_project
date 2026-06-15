
from __future__ import annotations

import argparse
from pathlib import Path

from .adapter.v13_adapter import records_from_v13_output
from .delivery.catalog_delivery import write_catalog_from_records
from .guardrails import assert_project_boundaries


def main() -> None:
    parser = argparse.ArgumentParser(description="Create v14 catalog TIFF delivery from existing v13 output.")
    parser.add_argument("--v13-output", required=True, help="Path to an existing v13 output folder.")
    parser.add_argument("--out", required=True, help="Output folder for catalog delivery.")
    parser.add_argument("--title", default="Bottom box refinement - right-strip cover")
    parser.add_argument("--skip-boundary-audit", action="store_true")
    args = parser.parse_args()

    pkg_dir = Path(__file__).resolve().parent
    if not args.skip_boundary_audit:
        assert_project_boundaries(pkg_dir)

    records = records_from_v13_output(args.v13_output)
    write_catalog_from_records(records, args.out, title=args.title)
    print(args.out)


if __name__ == "__main__":
    main()
