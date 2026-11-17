#!/usr/bin/env python3
"""Vérifie que tous les liens relatifs des documents Markdown (README.md et docs/) pointent vers un fichier existant."""
import pathlib, re, sys
root = pathlib.Path(__file__).resolve().parent.parent
bad = []
for f in list(root.glob("docs/**/*.md")) + [root / "README.md"]:
    for m in re.finditer(r"\]\(([^)\s]+)\)", f.read_text()):
        link = m.group(1)
        if link.startswith(("http", "mailto:", "#")):
            continue
        path = link.split("#")[0]
        if path and not (f.parent / path).exists():
            bad.append(f"{f.relative_to(root)} -> {link}")
print("\n".join(bad) or "tous les liens relatifs sont valides")
sys.exit(1 if bad else 0)
