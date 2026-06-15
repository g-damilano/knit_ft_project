from __future__ import annotations

from pathlib import Path
import sys

if __package__:
    from .analysis.knit_grid_literature_guided_v13 import *  # noqa: F401,F403
    from .analysis.knit_grid_literature_guided_v13 import main
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from knit_grid_catalog_delivery_v14.analysis.knit_grid_literature_guided_v13 import *  # noqa: F401,F403
    from knit_grid_catalog_delivery_v14.analysis.knit_grid_literature_guided_v13 import main


if __name__ == "__main__":
    main()
