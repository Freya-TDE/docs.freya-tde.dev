#!/usr/bin/env python3
"""Baut docs.freya-tde.dev: sammelt die Doku aus den Repos und baut je Sprache ein mdBook.

Builds docs.freya-tde.dev: collects the docs from the program repositories and builds one
mdBook per language (German at /de/, English at /en/, a language chooser at /).

Quellen / sources (je ein Repository-Ordner):
    FREYA_TDE_SRC  Freya-TDE  (docs/de, docs/en)        Vorgabe: sources/Freya-TDE
    RUF_SRC        RUF        (docs/de, docs/en)        Vorgabe: sources/RUF
    CTE_SRC        CT-E       (docs/de, docs/en, docs/images)  Vorgabe: sources/CT-E

Aufruf / usage:
    python3 tools/build.py            # baut nach public/
    python3 tools/build.py --serve de # Vorschau eines Buchs mit mdbook serve

Nur Python-Standardbibliothek; braucht `mdbook` (0.5) im PATH.
"""

from __future__ import annotations

import argparse
import json
import os
import posixpath
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
BUILD = ROOT / "build"
PUBLIC = ROOT / "public"
LANGS = ("de", "en")
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}


@dataclass
class Part:
    """Ein Teil des Buchs: die Doku eines Repositorys."""

    key: str  # Ordner im Buch / folder in the book
    env: str
    default: str
    github: str  # owner/name
    titles: dict[str, str]
    root: Path = field(default=Path())

    def docs(self, lang: str) -> Path:
        return self.root / "docs" / lang


PARTS = [
    Part("freya-tde", "FREYA_TDE_SRC", "sources/Freya-TDE", "Freya-TDE/Freya-TDE",
         {"de": "Freya TDE", "en": "Freya TDE"}),
    Part("ruf", "RUF_SRC", "sources/RUF", "Freya-TDE/RUF",
         {"de": "RUF & RNCL", "en": "RUF & RNCL"}),
    Part("ct-editor", "CTE_SRC", "sources/CT-E", "Freya-TDE/CT-E",
         {"de": "CT-Editor", "en": "CT-Editor"}),
]

# Unterordner eines Repos, die selbst ein Teil dieses Buchs sind (Freya-TDE bindet RUF und
# CT-E als Submodule ein): Repo-Pfad-Präfix → Teil.
SUBMODULES = {"RUF/": "ruf", "CT-Editor/": "ct-editor"}

LINK = re.compile(r"(!?)\[([^\]]*)\]\(([^)\s]+)\)")
HEADING = re.compile(r"^#\s+(.+?)\s*$", re.M)
# Zeile, die nur auf die andere Sprachfassung verweist („🇬🇧 English version“).
LANG_LINE = re.compile(r"^\s*(🇬🇧|🇩🇪)\s*\[[^\]]+\]\(\.\./(de|en)/[^)]*\)\s*$")


def fail(message: str) -> None:
    sys.exit(f"build.py: {message}")


def locate_sources() -> None:
    for part in PARTS:
        root = Path(os.environ.get(part.env, ROOT / part.default)).expanduser().resolve()
        for lang in LANGS:
            if not (root / "docs" / lang).is_dir():
                fail(f"{root / 'docs' / lang} fehlt – {part.env} auf den Ordner des Repositorys "
                     f"{part.github} setzen (oder es nach {part.default} klonen).")
        part.root = root


def title_of(path: Path) -> str:
    match = HEADING.search(path.read_text(encoding="utf-8"))
    return match.group(1) if match else path.stem


def chapter_order(part: Part, lang: str) -> list[str]:
    """Kapitel in der Reihenfolge, in der die README sie verlinkt; übrige danach."""
    docs = part.docs(lang)
    files = sorted(p.name for p in docs.glob("*.md") if p.name != "README.md")
    readme = (docs / "README.md").read_text(encoding="utf-8")
    order: list[str] = []
    for _, _, target in LINK.findall(readme):
        name = target.split("#")[0]
        if name in files and name not in order:
            order.append(name)
    rest = [f for f in files if f not in order]
    for name in rest:
        print(f"Hinweis: {part.key}/{lang}/{name} ist in der README nicht verlinkt", file=sys.stderr)
    return order + rest


class Rewriter:
    """Passt Verweise einer kopierten Datei an das Buch an."""

    def __init__(self, lang: str, files: dict[Path, str]):
        self.lang = lang
        self.files = files  # Quelldatei → Pfad im Buch (relativ zu src/)
        self.images: dict[Path, str] = {}

    def github(self, part: Part, rel: str, is_dir: bool) -> str:
        kind = "tree" if is_dir else "blob"
        return f"https://github.com/{part.github}/{kind}/main/{rel}"

    def in_book(self, part_key: str, lang: str, name: str) -> str | None:
        part = next(p for p in PARTS if p.key == part_key)
        source = (part.docs(lang) / name).resolve()
        if lang == self.lang:
            return self.files.get(source)
        return None

    def target(self, part: Part, source: Path, dest: str, target: str) -> str:
        if re.match(r"^[a-z][a-z0-9+.-]*:", target) or target.startswith("#"):
            return self.absolute(target, dest)
        path, _, anchor = target.partition("#")
        anchor = f"#{anchor}" if anchor else ""
        resolved = (source.parent / path).resolve()
        here = posixpath.dirname(dest)
        if resolved in self.files:
            return posixpath.relpath(self.files[resolved], here or ".") + anchor
        if resolved.suffix.lower() in IMAGE_SUFFIXES and resolved.is_file():
            book_path = self.images.setdefault(resolved, f"{part.key}/images/{resolved.name}")
            return posixpath.relpath(book_path, here or ".")
        # Dieselbe Doku in der anderen Sprache (z. B. „../en/release.md“).
        other = next((l for l in LANGS if l != self.lang), None)
        if other and resolved.is_relative_to(part.docs(other)):
            name = resolved.relative_to(part.docs(other)).as_posix()
            return self.other_language(dest, f"{part.key}/{name}") + anchor
        if resolved.is_relative_to(part.root):
            rel = resolved.relative_to(part.root).as_posix()
            for prefix, key in SUBMODULES.items():
                if rel.startswith(prefix):
                    sub = next(p for p in PARTS if p.key == key)
                    rest = rel[len(prefix):]
                    for lang in LANGS:
                        docs = f"docs/{lang}/"
                        if rest.startswith(docs):
                            mapped = self.in_book(key, lang, rest[len(docs):])
                            if mapped:
                                return posixpath.relpath(mapped, here or ".") + anchor
                    return self.github(sub, rest, resolved.is_dir()) + anchor
            return self.github(part, rel, resolved.is_dir()) + anchor
        print(f"Warnung: Verweis außerhalb des Repos in {source}: {target}", file=sys.stderr)
        return target

    def absolute(self, target: str, dest: str) -> str:
        """GitHub-Adressen auf Doku, die im Buch liegt, werden zu Verweisen im Buch."""
        here = posixpath.dirname(dest)
        for part in PARTS:
            prefix = f"https://github.com/{part.github}/blob/main/docs/{self.lang}/"
            if target.startswith(prefix):
                name, _, anchor = target[len(prefix):].partition("#")
                mapped = self.in_book(part.key, self.lang, name)
                if mapped:
                    return posixpath.relpath(mapped, here or ".") + (f"#{anchor}" if anchor else "")
        return target

    def other_language(self, dest: str, book_path: str) -> str:
        other = next(l for l in LANGS if l != self.lang)
        depth = dest.count("/")
        html = re.sub(r"(^|/)README\.md$", r"\1index.html", book_path)
        html = re.sub(r"\.md$", ".html", html)
        return "../" * (depth + 1) + f"{other}/{html}"

    def rewrite(self, part: Part, source: Path, dest: str, text: str) -> str:
        lines = [line for line in text.splitlines() if not LANG_LINE.match(line)]
        out = []
        in_code = False
        for line in lines:
            if line.lstrip().startswith("```"):
                in_code = not in_code
            if in_code:
                out.append(line)
                continue
            out.append(LINK.sub(
                lambda m: f"{m.group(1)}[{m.group(2)}]({self.target(part, source, dest, m.group(3))})",
                line,
            ))
        return "\n".join(out) + "\n"


def assemble(lang: str) -> list[str]:
    """Legt build/<lang>/ an; liefert die Seiten in Buchreihenfolge (für die Sprachzuordnung)."""
    book = BUILD / lang
    src = book / "src"
    shutil.rmtree(book, ignore_errors=True)
    src.mkdir(parents=True)

    plan: list[tuple[Part, Path, str]] = []  # (Teil, Quelle, Pfad im Buch)
    for part in PARTS:
        docs = part.docs(lang)
        plan.append((part, docs / "README.md", f"{part.key}/README.md"))
        for name in chapter_order(part, lang):
            plan.append((part, docs / name, f"{part.key}/{name}"))
    files = {source.resolve(): dest for _, source, dest in plan}
    rewriter = Rewriter(lang, files)

    for part, source, dest in plan:
        text = source.read_text(encoding="utf-8")
        target = src / dest
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rewriter.rewrite(part, source, dest, text), encoding="utf-8")
    for image, dest in rewriter.images.items():
        (src / dest).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(image, src / dest)

    # Einführung, Inhaltsverzeichnis, Buch-Einstellungen, Stil und Skripte.
    shutil.copy2(SITE / f"intro.{lang}.md", src / "README.md")
    summary = [("Einführung" if lang == "de" else "Introduction", "README.md")]
    lines = ["# Summary", "", f"[{summary[0][0]}](README.md)", ""]
    pages = ["README.md"]
    current = None
    for part, source, dest in plan:
        if part is not current:
            lines += ["", f"# {part.titles[lang]}", ""]
            current = part
            lines.append(f"- [{title_of(source)}]({dest})")
        else:
            lines.append(f"    - [{title_of(source)}]({dest})")
        pages.append(dest)
    (src / "SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    book_toml = (SITE / "book.toml").read_text(encoding="utf-8")
    title = "Freya TDE – Dokumentation" if lang == "de" else "Freya TDE – Documentation"
    book_toml = book_toml.replace("@TITLE@", title).replace("@LANG@", lang)
    (book / "book.toml").write_text(book_toml, encoding="utf-8")
    for name in ("freya.css", "freya.js"):
        shutil.copy2(SITE / name, book / name)
    return pages


def page_url(path: str) -> str:
    path = re.sub(r"(^|/)README\.md$", r"\1index.html", path)
    return re.sub(r"\.md$", ".html", path)


def write_language_map(pages: dict[str, list[str]]) -> None:
    """Ordnet jeder Seite die Seite derselben Stelle in der anderen Sprache zu."""
    de, en = pages["de"], pages["en"]
    if len(de) != len(en):
        print(f"Warnung: {len(de)} deutsche, {len(en)} englische Seiten – Zuordnung unvollständig",
              file=sys.stderr)
    pairs = list(zip(map(page_url, de), map(page_url, en)))
    for lang in LANGS:
        mapping = {a: b for a, b in pairs} if lang == "de" else {b: a for a, b in pairs}
        other = "en" if lang == "de" else "de"
        label = "English" if lang == "de" else "Deutsch"
        script = (f"window.FREYA_LANG = {json.dumps({'lang': lang, 'other': other, 'label': label, 'map': mapping}, ensure_ascii=False)};\n")
        (BUILD / lang / "freya-lang.js").write_text(script, encoding="utf-8")


def build() -> None:
    locate_sources()
    pages = {lang: assemble(lang) for lang in LANGS}
    write_language_map(pages)
    shutil.rmtree(PUBLIC, ignore_errors=True)
    PUBLIC.mkdir()
    for lang in LANGS:
        subprocess.run(["mdbook", "build", str(BUILD / lang), "--dest-dir", str(PUBLIC / lang)],
                       check=True)
    for name in ("index.html", "favicon.svg", "CNAME"):
        if (SITE / name).is_file():
            shutil.copy2(SITE / name, PUBLIC / name)
    print(f"fertig: {PUBLIC}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--serve", choices=LANGS, help="ein Buch mit mdbook serve ansehen")
    args = parser.parse_args()
    if args.serve:
        locate_sources()
        pages = {lang: assemble(lang) for lang in LANGS}
        write_language_map(pages)
        subprocess.run(["mdbook", "serve", str(BUILD / args.serve), "--open"], check=False)
    else:
        build()


if __name__ == "__main__":
    main()
