from __future__ import annotations

from pathlib import Path
import sys

if __package__:
    from .interface.dropbox_gui import *  # noqa: F401,F403
    from .interface.dropbox_gui import main
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from knit_grid_catalog_delivery_v14.interface.dropbox_gui import *  # noqa: F401,F403
    from knit_grid_catalog_delivery_v14.interface.dropbox_gui import main


if __name__ == "__main__":
    main()
