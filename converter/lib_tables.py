#!/usr/bin/env python3
"""
lib_tables - generuje tablice bibliotek KiCada (sym-lib-table, fp-lib-table) z zawartosci repozytorium SVN
(wywolywane z hooka post-commit).

KiCad czyta biblioteki Altium tylko pojedynczymi plikami, jeden wiersz tablicy na plik .SchLib / .PcbLib,
a nickname biblioteki to nazwa pliku bez katalogu i rozszerzenia - dokladnie to, co widoki bazy podaja w
kolumnach Symbols/Footprints. Dlatego po kazdym commicie, ktory dodal albo usunal taki plik, tablice sa
budowane od nowa i commitowane do kicad_tables/ jako kolejna rewizja autora kicad-tables-bot.

URI zaczynaja sie od ${ONYKS_LIBRARY}: zmienna srodowiskowa KiCada (Preferences -> Configure Paths)
wskazujaca na katalog roboczy SVN, czyli ten, w ktorym leza symbols/, footprints/ i kicad_tables/.

Uzycie:
    python3 lib_tables.py REPOS REV          (tylko jesli rewizja dodala/usunela plik biblioteki)
    python3 lib_tables.py REPOS --force      (zawsze, np. pierwsze wygenerowanie na istniejacym repozytorium)
"""
import argparse
import datetime
import os
import pathlib
import subprocess
import sys
import tempfile

BOT = "kicad-tables-bot"
TABLES_DIR = "kicad_tables"
VARIABLE = "ONYKS_LIBRARY"
# (folder, rozszerzenie pliku, plik tablicy, naglowek tablicy)
TABLES = [
    ("symbols", ".schlib", "sym-lib-table", "sym_lib_table"),
    ("footprints", ".pcblib", "fp-lib-table", "fp_lib_table"),
]


def log(rev, msg):
    print("%s r%s lib_tables: %s" % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), rev, msg), flush=True)


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        raise RuntimeError("%s\n%s%s" % (" ".join(cmd), r.stdout, r.stderr))
    return r.stdout


def touches_libraries(repos, rev):
    # svnlook changed: 4 znaki statusu, potem sciezka. Zmiana zawartosci (U) nie zmienia tablicy.
    for line in run(["svnlook", "changed", "-r", rev, repos]).splitlines():
        status, path = line[:4], line[4:].lower()
        if status[0] not in "AD":
            continue
        for folder, extension, _, _ in TABLES:
            if path.startswith(folder + "/") and path.endswith(extension):
                return True
    return False


def quoted(text):
    return '"%s"' % text.replace("\\", "\\\\").replace('"', '\\"')


def build_table(tree, folder, extension, header):
    """Zwraca (tekst tablicy, lista pominietych sciezek). Pliki po sciezce, wiec wynik jest stabilny."""
    rows, seen, skipped = [], {}, []
    for path in sorted(p for p in tree if p.startswith(folder + "/") and p.lower().endswith(extension)):
        nickname = os.path.basename(path)[:-len(extension)]
        if nickname in seen:
            skipped.append("%s (nickname jak %s)" % (path, seen[nickname]))
            continue
        seen[nickname] = path
        rows.append("  (lib (name %s)(type \"Altium\")(uri %s)(options \"\")(descr \"\"))"
                    % (quoted(nickname), quoted("${%s}/%s" % (VARIABLE, path))))
    return "(%s\n  (version 7)\n%s\n)\n" % (header, "\n".join(rows)), skipped


def current(repos, path):
    r = subprocess.run(["svnlook", "cat", repos, path], capture_output=True)
    return r.stdout.decode("utf-8", errors="replace") if r.returncode == 0 else None


def regenerate(repos, rev):
    tree = [line.strip() for line in run(["svnlook", "tree", "--full-paths", repos]).splitlines()]
    actions, summary = [], []
    with tempfile.TemporaryDirectory(prefix="lib-tables-") as tmp:
        for folder, extension, filename, header in TABLES:
            text, skipped = build_table(tree, folder, extension, header)
            for s in skipped:
                log(rev, "POMINIETO, ten sam nickname: %s" % s)
            target = "%s/%s" % (TABLES_DIR, filename)
            if current(repos, target) == text:
                continue
            local = os.path.join(tmp, filename)
            with open(local, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
            actions.append(["put", local, target])
            summary.append("%s: %d wierszy" % (filename, text.count("\n  (lib ")))
        if not actions:
            log(rev, "tablice aktualne")
            return
        if TABLES_DIR + "/" not in tree:
            actions.insert(0, ["mkdir", TABLES_DIR])
        cmd = ["svnmucc", "--non-interactive", "--username", BOT, "-U",
               pathlib.Path(repos).resolve().as_uri(), "-m",
               "kicad-tables: r%s (%s)" % (rev, ", ".join(summary))]
        for action in actions:
            cmd += action
        log(rev, run(cmd).strip().splitlines()[-1] + " (" + ", ".join(summary) + ")")


def main():
    ap = argparse.ArgumentParser(description="Hook post-commit: tablice bibliotek KiCada")
    ap.add_argument("repos", help="sciezka do repozytorium (pierwszy argument hooka)")
    ap.add_argument("rev", nargs="?", default="?", help="numer rewizji (drugi argument hooka)")
    ap.add_argument("--force", action="store_true", help="generuj niezaleznie od zawartosci rewizji")
    a = ap.parse_args()
    if not a.force:
        if a.rev == "?":
            ap.error("podaj REV albo --force")
        if not touches_libraries(a.repos, a.rev):
            return
    regenerate(a.repos, a.rev)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(sys.argv[2] if len(sys.argv) > 2 else "?", "BLAD: %s" % e)
        sys.exit(1)
