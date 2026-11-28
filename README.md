# docs.freya-tde.dev

Die Dokumentation des Projekts [Freya TDE](https://freya-tde.dev) – je Sprache ein
[mdBook](https://rust-lang.github.io/mdBook/) (≥ 0.5): Deutsch unter `/de/`, Englisch unter `/en/`,
eine Sprachwahl unter `/`. Der Inhalt liegt **nicht hier**, sondern in den Repositorys der Programme
und wird beim Bauen eingesammelt:

*The documentation of the Freya TDE project – one mdBook per language. The content lives in the
program repositories and is collected at build time:*

| Teil / part | Quelle / source |
|---|---|
| Freya TDE – Handbuch | [`Freya-TDE/Freya-TDE`](https://github.com/Freya-TDE/Freya-TDE) `docs/de`, `docs/en` |
| RUF & RNCL | [`Freya-TDE/RUF`](https://github.com/Freya-TDE/RUF) `docs/de`, `docs/en` |
| CT-Editor | [`Freya-TDE/CT-E`](https://github.com/Freya-TDE/CT-E) `docs/de`, `docs/en` |

## Bauen / build

```sh
# Repositorys nach sources/ klonen – oder auf vorhandene Ordner zeigen:
FREYA_TDE_SRC=~/…/Freya-TDE RUF_SRC=~/…/RUF CTE_SRC=~/…/CT-E python3 tools/build.py
python3 -m http.server -d public 8000      # Vorschau: http://127.0.0.1:8000
python3 tools/build.py --serve de          # ein Buch mit Live-Neuladen (mdbook serve)
```

`tools/build.py` (nur Python-Standardbibliothek):

- kopiert die Kapitel in der Reihenfolge, in der die `README.md` des Teils sie verlinkt, und erzeugt
  daraus das Inhaltsverzeichnis (Titel = erste Überschrift);
- schreibt Verweise um: Kapitel im Buch bleiben Verweise im Buch, andere Dateien der Repos werden zu
  GitHub-Adressen, Bilder werden mitkopiert, die Zeile „English version“ entfällt;
- ordnet jeder Seite die Seite an derselben Stelle der anderen Sprache zu (Sprachumschalter oben rechts).

`site/` enthält Buch-Einstellungen (`book.toml`), Farben (`freya.css`, `#990000` = Hausfarbe, hell /
dunkel / System), den Sprachumschalter (`freya.js`), die Einführungsseiten und die Sprachwahl
(`index.html`).

## Veröffentlichen / publish

Der Workflow `.github/workflows/pages.yml` baut bei jedem Push, von Hand, auf ein
`repository_dispatch` vom Typ `docs` aus einem Programm-Repo und täglich um 04:17 UTC (so kommen
Doku-Änderungen aus Freya-TDE, RUF und CT-E ohne Token an). Voraussetzung: öffentliches Repository,
*Settings → Pages → Source: GitHub Actions* (bei „Deploy from a branch“ versucht GitHub zusätzlich einen
Jekyll-Build, der an mdBook scheitert), Domain `docs.freya-tde.dev` (Datei `site/CNAME`).
*Builds on push, by hand, on a `docs` dispatch and daily; Pages source must be "GitHub Actions".*

Lizenz / license: MIT OR Apache-2.0, © Dragon Software.
