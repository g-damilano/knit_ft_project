from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    args = sys.argv[1:]
    if args and args[0] == "--run-v13":
        try:
            from ..analysis.knit_grid_literature_guided_v13 import main as v13_main
        except ImportError:
            sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
            from knit_grid_catalog_delivery_v14.analysis.knit_grid_literature_guided_v13 import main as v13_main

        sys.argv = [sys.argv[0], *args[1:]]
        v13_main()
        return
    if args and args[0] == "--run-delivery":
        try:
            from ..cli import main as delivery_main
        except ImportError:
            sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
            from knit_grid_catalog_delivery_v14.cli import main as delivery_main

        delivery_args = list(args[1:])
        if getattr(sys, "frozen", False) and "--skip-boundary-audit" not in delivery_args:
            delivery_args.append("--skip-boundary-audit")
        sys.argv = [sys.argv[0], *delivery_args]
        delivery_main()
        return
    # GUI path — only import PySide6 here, not for --run-v13 / --run-delivery
    try:
        from ..interface.dropbox_gui import main as gui_main
    except ImportError:
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
        from knit_grid_catalog_delivery_v14.interface.dropbox_gui import main as gui_main
    gui_main()


if __name__ == "__main__":
    main()
