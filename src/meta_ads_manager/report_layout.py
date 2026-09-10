"""One HTML entrypoint with supporting files kept in a single materials directory."""

from pathlib import Path

from meta_ads_manager.errors import AppError

MATERIALS = "materialy"
HTML = "raport.html"


def materials_directory(root: Path, create=False) -> Path:
    target = root / MATERIALS
    if target.is_symlink() or root.is_symlink():
        raise AppError("REPORT_LAYOUT", "Katalog raportu nie może być dowiązaniem.", 2)
    # Continue an older collection in place until a successful render bundles it.
    if (root / "collection.json").is_file() or (root / "scope.json").is_file():
        if (target / "collection.json").exists() or (target / "scope.json").exists():
            raise AppError("REPORT_LAYOUT", "Dwie kolekcje w jednym katalogu raportu.", 2)
        return root
    if create:
        target.mkdir(parents=True, exist_ok=True, mode=0o700)
    return target


def input_path(root: Path, path: Path) -> Path:
    if path.exists():
        return path
    # Old CLI invocations remain usable after their supporting files have moved.
    try:
        relative = path.absolute().relative_to(root.absolute())
    except ValueError:
        return path
    return root / MATERIALS / relative


def bundle(root: Path, html: str, markdown: str, metrics: str) -> dict:
    target = root / MATERIALS
    if any(
        (root / name).exists() for name in ("workspace.json", "AGENTS.md", ".git", "pyproject.toml")
    ):
        raise AppError("REPORT_LAYOUT", "Wskaż osobny katalog jednego raportu.", 2)
    if root.is_symlink() or target.is_symlink() or (root / HTML).is_symlink():
        raise AppError("REPORT_LAYOUT", "Dowiązania nie są obsługiwane przy składaniu raportu.", 2)
    moving = [p for p in root.iterdir() if p.name not in (MATERIALS, HTML)]
    if any(p.is_symlink() or (target / p.name).exists() for p in moving):
        raise AppError("REPORT_LAYOUT", "Kolizja nazw materiałów; niczego nie przeniesiono.", 2)
    for output in (root / HTML, target / "report.md", target / "report-metrics.json"):
        if output.exists() and not output.is_file():
            raise AppError("REPORT_LAYOUT", "Ścieżka wyniku nie jest plikiem.", 2)
    for name in ("report.md", "report-metrics.json"):
        if (target / name).is_symlink():
            raise AppError("REPORT_LAYOUT", "Plik materiału jest dowiązaniem.", 2)
    target.mkdir(exist_ok=True, mode=0o700)
    for path in moving:
        path.rename(target / path.name)
    for path, content in (
        (root / HTML, html),
        (target / "report.md", markdown),
        (target / "report-metrics.json", metrics),
    ):
        path.write_text(content, encoding="utf-8")
        path.chmod(0o600)
    return {
        "html": str((root / HTML).resolve()),
        "markdown": str((target / "report.md").resolve()),
        "materials": str(target.resolve()),
    }
