#!/usr/bin/env python3
"""Met à jour les boîtes « Mots à connaître » des documents à partir du glossaire (source unique : docs/sre/GLOSSAIRE.md).

Dans un document, on écrit :
    <!-- mots: token, prefill, ttft -->
    <!-- /mots -->
et ce script remplit l'espace entre les deux repères avec les définitions du glossaire (une ligne par mot).
Usage : tests/gen_doc_boxes.py            réécrit les boîtes
        tests/gen_doc_boxes.py --check    échoue si une boîte est périmée ou si un mot est introuvable (utilisé par tests/static.sh)"""
import pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
GLOSS = ROOT / "docs/sre/GLOSSAIRE.md"
ROW = re.compile(r"^\|\s*\*\*(.+?)\*\*\s*\|\s*(.+?)\s*\|\s*$")


def norm(s):
    s = s.replace("`", "").lower()
    s = re.sub(r"\s*\(.*?\)", "", s)
    return s.strip()


def load():
    terms = {}
    for line in GLOSS.read_text().splitlines():
        m = ROW.match(line)
        if not m:
            continue
        label, definition = m.group(1), m.group(2)
        for alias in re.split(r"\s+/\s+", label):
            terms.setdefault(norm(alias), (label, definition))
    return terms


def box(keys, terms, rel):
    lines = ["> **Mots à connaître**"]
    seen = set()
    for k in keys:
        key = norm(k)
        if key not in terms:
            raise KeyError(f"mot introuvable dans le glossaire : {k!r}")
        label, definition = terms[key]
        if label in seen:   # deux clés peuvent désigner la même ligne du glossaire (ex. « page » et « ticket »)
            continue
        seen.add(label)
        lines.append(f"> - **{label}** : {definition}")
    lines.append(f"> - Tous les mots : [glossaire]({rel}).")
    return "\n".join(lines)


def main(check):
    terms = load()
    bad = 0
    pat = re.compile(r"(<!-- mots: (.*?) -->)\n(.*?)(<!-- /mots -->)", re.S)
    for f in sorted(ROOT.glob("**/*.md")):
        if ".git" in f.parts or "results" in f.parts:
            continue
        text = f.read_text()
        if "<!-- mots:" not in text:
            continue
        rel = pathlib.Path(__import__("os").path.relpath(GLOSS, f.parent)).as_posix()

        def repl(m):
            keys = [k.strip() for k in m.group(2).split(",") if k.strip()]
            return f"{m.group(1)}\n{box(keys, terms, rel)}\n{m.group(4)}"

        try:
            new = pat.sub(repl, text)
        except KeyError as e:
            print(f"ERREUR {f.relative_to(ROOT)} : {e}")
            bad += 1
            continue
        if new != text:
            if check:
                print(f"PÉRIMÉ {f.relative_to(ROOT)} (lancer tests/gen_doc_boxes.py)")
                bad += 1
            else:
                f.write_text(new)
                print(f"mis à jour {f.relative_to(ROOT)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main("--check" in sys.argv))
