from __future__ import annotations

from pathlib import Path
import subprocess
import sys


def main() -> None:
    package_dir = Path(__file__).resolve().parents[1]
    project_root = Path(__file__).resolve().parents[3]
    entry = package_dir / "production" / "launcher.py"
    dist_dir = project_root / "dist"
    build_dir = project_root / "build"
    spec_dir = project_root / "build_specs"

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name",
        "KnitGridCatalogDelivery",
        "--paths",
        str(project_root / "src"),
        "--collect-submodules",
        "knit_grid_catalog_delivery_v14",
        "--distpath",
        str(dist_dir),
        "--workpath",
        str(build_dir),
        "--specpath",
        str(spec_dir),
        str(entry),
    ]

    try:
        subprocess.run(cmd, check=True)
    except FileNotFoundError as exc:
        raise SystemExit("PyInstaller is not installed. Run: python -m pip install pyinstaller") from exc
    except subprocess.CalledProcessError as exc:
        raise SystemExit(exc.returncode) from exc

    exe = dist_dir / ("KnitGridCatalogDelivery.exe" if sys.platform.startswith("win") else "KnitGridCatalogDelivery")
    readme = dist_dir / "README_DISTRIBUTION.txt"
    readme.write_text(
        "Knit Grid Catalog Delivery\n"
        "==========================\n\n"
        "This distribution is self-contained for normal use.\n"
        "Open KnitGridCatalogDelivery.exe, load a swatch image, load or edit the YAML metadata, choose an output folder, and run the catalog.\n\n"
        "No Python installation, source checkout, analyzer path, package path, or external library install is needed to run this executable.\n\n"
        "The bundled analysis path includes optional Numba acceleration when this executable is built from requirements-production.txt.\n\n"
        "Expected inputs:\n"
        "- image: .png, .jpg, .jpeg, .tif, .tiff, or .webp\n"
        "- optional metadata sidecar: .yaml or .yml\n\n"
        "The app writes a run folder containing:\n"
        "- copied source image and YAML metadata\n"
        "- analysis/v13 output\n"
        "- delivery/catalog output with cover PNGs, layered TIFF, and JSON metadata\n",
        encoding="utf-8",
    )
    print(f"Executable written to: {exe}")
    print(f"Distribution notes written to: {readme}")


if __name__ == "__main__":
    main()
