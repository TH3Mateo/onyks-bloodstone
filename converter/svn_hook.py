#!/usr/bin/env python3
"""
svn_hook - konwersja bibliotek KiCad wrzuconych do SVN na biblioteki Altium (wywolywane z hooka post-commit).

Jesli autor rewizji jest uzytkownikiem KiCad (tool = 'kicad' w private.users), kazdy dodany lub zmieniony
plik .kicad_sym / .kicad_mod jest konwertowany przez kicad2altium.py do .SchLib / .PcbLib o tej samej nazwie
w tym samym katalogu, a oryginal jest usuwany z repozytorium. Wszystko trafia do jednego commita autora
kicad2altium-bot (nazwa z myslnikiem, wiec nie moze sie pokryc z loginem z bazy).

Uzycie:
    python3 svn_hook.py REPOS REV --users-file /etc/svn-kicad-users
    python3 svn_hook.py REPOS REV --all-users      (bez sprawdzania autora, do testow)
"""
import argparse
import datetime
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

BOT = "kicad2altium-bot"
CONVERTER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kicad2altium.py")
CONVERSIONS = {".kicad_sym": (".SchLib", "--sym"), ".kicad_mod": (".PcbLib", "--fp")}


def log(rev, msg):
    print("%s r%s %s" % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), rev, msg), flush=True)


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        raise RuntimeError("%s\n%s%s" % (" ".join(cmd), r.stdout, r.stderr))
    return r.stdout


def kicad_users(path):
    try:
        with open(path, encoding="utf-8") as f:
            return {line.strip() for line in f if line.strip()}
    except OSError:
        return set()


def changed_kicad_files(repos, rev):
    # svnlook changed: 4 znaki statusu, potem sciezka; katalogi koncza sie na '/'
    out = []
    for line in run(["svnlook", "changed", "-r", rev, repos]).splitlines():
        status, path = line[:4], line[4:]
        if status[0] in "AUR" and os.path.splitext(path)[1] in CONVERSIONS:
            out.append(path)
    return out


def convert_and_commit(repos, rev, author, paths):
    tmp = tempfile.mkdtemp(prefix="kicad2altium-")
    try:
        svn = ["svn", "--non-interactive", "--config-dir", os.path.join(tmp, "config")]
        wc = os.path.join(tmp, "wc")
        # rzadka kopia robocza: tylko zmienione pliki i ich ewentualne odpowiedniki Altium
        run(svn + ["checkout", "--depth", "empty", pathlib.Path(repos).resolve().as_uri(), wc])
        done = []
        for path in paths:
            ext = os.path.splitext(path)[1]
            new_ext, flag = CONVERSIONS[ext]
            target = path[:-len(ext)] + new_ext
            src, dst = os.path.join(wc, path), os.path.join(wc, target)
            run(svn + ["update", "--parents", src, dst])
            if not os.path.isfile(src):
                log(rev, "%s: nie ma go juz w HEAD, pomijam" % path)
                continue
            r = subprocess.run([sys.executable, CONVERTER, flag, src, "-o", os.path.dirname(src)],
                               capture_output=True, text=True, encoding="utf-8", errors="replace")
            if r.returncode or not os.path.isfile(dst):
                log(rev, "%s: konwersja nieudana, plik zostaje w repozytorium\n%s%s" % (path, r.stdout, r.stderr))
                continue
            run(svn + ["add", "--force", dst])
            run(svn + ["delete", src])
            done.append((path, target))
            log(rev, "%s -> %s" % (path, target))
        if not done:
            return
        msg = "kicad2altium: konwersja r%s (%s)\n\n" % (rev, author)
        msg += "".join("%s -> %s\n" % d for d in done)
        out = run(svn + ["commit", "--username", BOT, "-m", msg, wc])
        log(rev, out.strip().splitlines()[-1])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description="Hook post-commit: KiCad -> Altium")
    ap.add_argument("repos", help="sciezka do repozytorium (pierwszy argument hooka)")
    ap.add_argument("rev", help="numer rewizji (drugi argument hooka)")
    ap.add_argument("--users-file", help="plik z loginami uzytkownikow KiCad, po jednym w linii")
    ap.add_argument("--all-users", action="store_true", help="konwertuj niezaleznie od autora")
    a = ap.parse_args()
    if not a.users_file and not a.all_users:
        ap.error("podaj --users-file albo --all-users")

    author = run(["svnlook", "author", "-r", a.rev, a.repos]).strip()
    if author == BOT:
        return
    if not a.all_users and author not in kicad_users(a.users_file):
        return
    paths = changed_kicad_files(a.repos, a.rev)
    if paths:
        convert_and_commit(a.repos, a.rev, author, paths)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(sys.argv[2] if len(sys.argv) > 2 else "?", "BLAD: %s" % e)
        sys.exit(1)
