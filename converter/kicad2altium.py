#!/usr/bin/env python3
"""
kicad2altium - konwerter bibliotek KiCad (.kicad_sym / .kicad_mod / .pretty) do Altium (.SchLib / .PcbLib).

Format wyjsciowy odtworzony na podstawie porownania wejscia i wyjscia oficjalnego importera KiCad w Altium
(katalog "Imported OPA1652AIDRGR") oraz parsera Altium w KiCad (altium_parser_sch / altium_parser_pcb).

Uzycie:
    python kicad2altium.py --sym OPA1652AIDRGR.kicad_sym --fp SON50P300X300X80-9N-D.kicad_mod -o out
    python kicad2altium.py --sym lib.kicad_sym --fp Moja.pretty -o out --name MojaBiblioteka
    python kicad2altium.py --fp Moja.pretty -o out --layer-map warstwy.json   (wlasne tlumaczenie warstw)
    python kicad2altium.py --dump out/MojaBiblioteka.SchLib     (podglad zawartosci, wymaga olefile)

Brak zewnetrznych zaleznosci (zapis plikow OLE/CFB zaimplementowany ponizej).
"""
import argparse
import datetime
import math
import os
import random
import re
import string
import struct
import sys

import altium_templates as tpl

WARNINGS = []


def warn(msg):
    WARNINGS.append(msg)
    print("  ! " + msg, file=sys.stderr)


# --------------------------------------------------------------------------------------------------
# S-expression
# --------------------------------------------------------------------------------------------------

_TOKEN_RE = re.compile(r'\s*(?:(\()|(\))|"((?:[^"\\]|\\.)*)"|([^\s()"]+))', re.S)


def parse_sexpr(text):
    stack = [[]]
    pos = 0
    n = len(text)
    while pos < n:
        m = _TOKEN_RE.match(text, pos)
        if not m:
            if text[pos:].strip() == "":
                break
            raise ValueError("Blad parsowania S-expr na pozycji %d" % pos)
        pos = m.end()
        if m.group(1):
            stack.append([])
        elif m.group(2):
            node = stack.pop()
            stack[-1].append(node)
        elif m.group(3) is not None:
            s = m.group(3)
            s = re.sub(r'\\(.)', lambda mm: {'n': '\n', 't': '\t'}.get(mm.group(1), mm.group(1)), s)
            stack[-1].append(Str(s))
        else:
            stack[-1].append(m.group(4))
    return stack[0][0]


class Str(str):
    """Napis w cudzyslowie (odroznienie od atomu)."""


def head(node):
    return node[0] if isinstance(node, list) and node else None


def find(node, name):
    for c in node[1:]:
        if isinstance(c, list) and c and c[0] == name:
            return c
    return None


def findall(node, name):
    return [c for c in node[1:] if isinstance(c, list) and c and c[0] == name]


def val(node, name, default=None, idx=1):
    c = find(node, name)
    if c is None or len(c) <= idx:
        return default
    return c[idx]


def fval(node, name, default=0.0, idx=1):
    v = val(node, name, None, idx)
    return float(v) if v is not None else default


def xy(node, name="at"):
    c = find(node, name)
    if c is None:
        return 0.0, 0.0, 0.0
    return float(c[1]), float(c[2]), (float(c[3]) if len(c) > 3 and not isinstance(c[3], list) else 0.0)


def has_flag(node, flag):
    """'hide' jako atom (stary format) albo (hide yes) (nowy)."""
    for c in node[1:]:
        if c == flag:
            return True
        if isinstance(c, list) and c and c[0] == flag:
            return len(c) == 1 or c[1] in ("yes", "true")
    return False


def text_hidden(node):
    if has_flag(node, "hide"):
        return True
    eff = find(node, "effects")
    return eff is not None and has_flag(eff, "hide")


def text_size(node, default=1.27):
    eff = find(node, "effects")
    font = find(eff, "font") if eff else None
    size = find(font, "size") if font else None
    return float(size[1]) if size else default


def text_justify(node):
    eff = find(node, "effects")
    j = find(eff, "justify") if eff else None
    return set(j[1:]) if j else set()


def fill_type(node):
    f = find(node, "fill")
    if f is None:
        return "none"
    t = val(f, "type")
    if t is None and len(f) > 1 and not isinstance(f[1], list):
        t = f[1]  # (fill solid) / (fill yes) w footprintach
    return {"yes": "solid", "no": "none"}.get(t, t or "none")


def stroke_width(node):
    s = find(node, "stroke")
    if s is not None:
        return fval(s, "width", 0.0)
    return fval(node, "width", 0.0)


# --------------------------------------------------------------------------------------------------
# Compound File Binary (OLE2) - minimalny zapis
# --------------------------------------------------------------------------------------------------

FREESECT, ENDOFCHAIN, FATSECT = 0xFFFFFFFF, 0xFFFFFFFE, 0xFFFFFFFD
NOSTREAM = 0xFFFFFFFF


class CfbNode:
    def __init__(self, name, data=None, clsid=b"\0" * 16):
        self.name = name
        self.data = data  # None => storage
        self.children = {}
        self.clsid = clsid

    def storage(self, name, clsid=b"\0" * 16):
        if name not in self.children:
            self.children[name] = CfbNode(name, None, clsid)
        return self.children[name]

    def stream(self, name, data):
        self.children[name] = CfbNode(name, bytes(data))


def _cfb_key(name):
    return (len(name), name.upper())


def write_cfb(root, path, root_clsid=b"\0" * 16):
    SS, MSS, CUTOFF = 512, 64, 4096
    entries = []  # (node, type)

    def add(node, typ):
        idx = len(entries)
        entries.append({"node": node, "type": typ, "left": NOSTREAM, "right": NOSTREAM, "child": NOSTREAM,
                        "start": ENDOFCHAIN, "size": 0})
        return idx

    def build_tree(idxs):
        # zbalansowane drzewo BST, wszystkie wezly czarne
        if not idxs:
            return NOSTREAM
        mid = len(idxs) // 2
        e = entries[idxs[mid]]
        e["left"] = build_tree(idxs[:mid])
        e["right"] = build_tree(idxs[mid + 1:])
        return idxs[mid]

    def walk(node, idx):
        kids = sorted(node.children.values(), key=lambda c: _cfb_key(c.name))
        kid_idx = [add(k, 2 if k.data is not None else 1) for k in kids]
        entries[idx]["child"] = build_tree(kid_idx)
        for k, ki in zip(kids, kid_idx):
            if k.data is None:
                walk(k, ki)

    root.clsid = root_clsid
    add(root, 5)
    walk(root, 0)

    # mini stream
    mini = bytearray()
    minifat = []
    big_streams = []
    for e in entries:
        if e["type"] != 2:
            continue
        d = e["node"].data
        e["size"] = len(d)
        if len(d) == 0:
            e["start"] = ENDOFCHAIN
        elif len(d) < CUTOFF:
            first = len(mini) // MSS
            cnt = (len(d) + MSS - 1) // MSS
            e["start"] = first
            minifat.extend(list(range(first + 1, first + cnt)) + [ENDOFCHAIN])
            mini += d + b"\0" * (cnt * MSS - len(d))
        else:
            big_streams.append(e)

    sectors = []  # lista (dane 512B)
    fat = []

    def alloc(data):
        if not data:
            return ENDOFCHAIN
        cnt = (len(data) + SS - 1) // SS
        first = len(sectors)
        data = data + b"\0" * (cnt * SS - len(data))
        for i in range(cnt):
            sectors.append(data[i * SS:(i + 1) * SS])
            fat.append(first + i + 1 if i < cnt - 1 else ENDOFCHAIN)
        return first

    minifat_bytes = b"".join(struct.pack("<I", v) for v in minifat)
    if minifat_bytes:
        pad = (-len(minifat_bytes)) % SS
        minifat_bytes += struct.pack("<I", FREESECT) * (pad // 4)
    minifat_start = alloc(minifat_bytes)
    minifat_count = len(minifat_bytes) // SS
    entries[0]["start"] = alloc(bytes(mini)) if mini else ENDOFCHAIN
    entries[0]["size"] = len(mini)
    for e in big_streams:
        e["start"] = alloc(e["node"].data)

    # katalog
    dirdata = bytearray()
    for e in entries:
        name = e["node"].name
        if len(name) > 31:
            raise ValueError("Nazwa OLE > 31 znakow: " + name)
        nm = name.encode("utf-16-le") + b"\0\0"
        dirdata += nm + b"\0" * (64 - len(nm))
        dirdata += struct.pack("<HBB", len(nm), e["type"], 1)
        dirdata += struct.pack("<III", e["left"], e["right"], e["child"])
        dirdata += e["node"].clsid if e["type"] != 2 else b"\0" * 16
        dirdata += struct.pack("<I", 0) + b"\0" * 16
        dirdata += struct.pack("<IQ", e["start"], e["size"])
    while len(dirdata) % SS:
        dirdata += (b"\0" * 64 + struct.pack("<HBB", 0, 0, 0) + struct.pack("<III", NOSTREAM, NOSTREAM, NOSTREAM)
                    + b"\0" * 36 + struct.pack("<IQ", 0, 0))
    dir_start = alloc(bytes(dirdata))

    # sektory FAT
    nfat = 1
    while (len(sectors) + nfat) > nfat * (SS // 4):
        nfat += 1
    if nfat > 109:
        raise ValueError("Plik zbyt duzy dla prostego zapisu CFB (DIFAT)")
    fat_start = len(sectors)
    fat.extend([FATSECT] * nfat)
    fat.extend([FREESECT] * (nfat * (SS // 4) - len(fat)))
    fat_bytes = b"".join(struct.pack("<I", v) for v in fat)
    for i in range(nfat):
        sectors.append(fat_bytes[i * SS:(i + 1) * SS])

    header = bytearray()
    header += bytes.fromhex("D0CF11E0A1B11AE1") + b"\0" * 16
    header += struct.pack("<HHHHH", 0x3E, 3, 0xFFFE, 9, 6) + b"\0" * 6
    header += struct.pack("<IIIIIIIII", 0, nfat, dir_start, 0, CUTOFF,
                          minifat_start if minifat_count else ENDOFCHAIN, minifat_count, ENDOFCHAIN, 0)
    difat = [fat_start + i for i in range(nfat)] + [FREESECT] * (109 - nfat)
    header += b"".join(struct.pack("<I", v) for v in difat)
    assert len(header) == 512
    with open(path, "wb") as f:
        f.write(header)
        for s in sectors:
            f.write(s)


# --------------------------------------------------------------------------------------------------
# Wspolne
# --------------------------------------------------------------------------------------------------

def uid8():
    return "".join(random.choice(string.ascii_uppercase) for _ in range(8))


def ole_name(name, used):
    """Nazwa storage w OLE: max 31 znakow, bez '/', '\\', ':', '!'."""
    n = re.sub(r'[/\\:!]', '_', name)[:31]
    base, k = n, 1
    while n.upper() in used:
        suffix = "~%d" % k
        n = base[:31 - len(suffix)] + suffix
        k += 1
    used.add(n.upper())
    return n


def enc(s):
    return s.encode("cp1252", errors="replace")


def props_record(props):
    """Rekord tekstowy |K=V|K=V\\0 (dla stringow non-ASCII dodaje %UTF8%K)."""
    out = bytearray()
    for k, v in props:
        if v is None:
            continue
        v = str(v)
        out += b"|" + enc(k) + b"=" + enc(v)
        if any(ord(c) > 127 for c in v):
            out += b"|%UTF8%" + enc(k) + b"=" + v.encode("utf-8")
    return bytes(out) + b"\0"


def sch_record(payload, binary=False):
    return struct.pack("<I", len(payload) | ((1 if binary else 0) << 24)) + payload


def pstr(s):
    b = enc(s)[:255]
    return bytes([len(b)]) + b


# --------------------------------------------------------------------------------------------------
# SchLib
# --------------------------------------------------------------------------------------------------

SCH_UNIT = 0.254  # 1 jednostka Altium Sch = 10 mil

ELEC = {"input": 0, "bidirectional": 1, "output": 2, "open_collector": 3, "passive": 4, "tri_state": 5,
        "open_emitter": 6, "power_in": 7, "power_out": 7, "free": 4, "unspecified": 4, "no_connect": 4}


def sch_coord(key, mm):
    v = mm / SCH_UNIT
    i = int(v)  # obciecie w strone zera, ulamek z tym samym znakiem
    frac = int(round((v - i) * 100000))
    if abs(frac) >= 100000:
        i += 1 if frac > 0 else -1
        frac = 0
    out = []
    if i:
        out.append((key, i))
    if frac:
        out.append((key + "_Frac", frac))
    return out


def sch_pt(kx, ky, x, y):
    return sch_coord(kx, x) + sch_coord(ky, y)


def sch_linewidth(w):
    if w <= 0.3:
        return 1
    if w <= 0.6:
        return 2
    return 3


def kicad_overbar(name):
    def bar(s):
        return "".join(c + "\\" for c in s)
    name = re.sub(r'~\{([^}]*)\}', lambda m: bar(m.group(1)), name)
    if "~" in name and name != "~":
        parts = name.split("~")
        name = "".join(bar(p) if i % 2 else p for i, p in enumerate(parts))
    return "" if name == "~" else name


def justification(just):
    h = 0 if "left" in just else (2 if "right" in just else 1)
    v = 2 if "top" in just else (0 if "bottom" in just else 1)
    return v * 3 + h


class FontTable:
    def __init__(self):
        self.fonts = [("Times New Roman", 10)]

    def get(self, size_mm):
        pt = max(4, int(round(size_mm * 8 / 1.27)))
        key = ("Arial", pt)
        if key not in self.fonts:
            self.fonts.append(key)
        return self.fonts.index(key) + 1


COLOR_LINE = 128          # ciemnoczerwony
COLOR_AREA = 11599871     # jasnozolty
COLOR_PARAM = 8388608
COLOR_DESIG = 8388608


def resolve_extends(symbols):
    by_name = {s[1]: s for s in symbols}
    out = []
    for s in symbols:
        ext = val(s, "extends")
        if ext and ext in by_name:
            parent = by_name[ext]
            merged = [s[0], s[1]] + [c for c in parent[2:]
                                     if not (isinstance(c, list) and c and c[0] == "property")]
            own_props = {p[1]: p for p in findall(s, "property")}
            parent_props = [p for p in findall(parent, "property") if p[1] not in own_props]
            merged += parent_props + list(own_props.values())
            out.append(merged)  # podsymbole rodzica zostaja z nazwa rodzica - liczy sie tylko sufiks _U_B
        else:
            out.append(s)
    return out


def build_sch_component(sym, fonts):
    name = sym[1]
    records = []
    props = {p[1]: p for p in findall(sym, "property")}

    def prop(n, d=""):
        return props[n][2] if n in props else d

    # podjednostki (unit, body style)
    units = {}
    for sub in findall(sym, "symbol"):
        m = re.match(r'.*_(\d+)_(\d+)$', sub[1])
        if not m:
            continue
        units.setdefault((int(m.group(1)), int(m.group(2))), []).append(sub)
    # stary format (np. SamacSys): grafika i piny bezposrednio w symbolu - traktuj jak unit 0
    direct = [c for c in sym[2:] if head(c) in ("rectangle", "polyline", "circle", "arc", "bezier", "text", "pin")]
    if direct:
        units.setdefault((0, 0), []).append(["symbol", Str("")] + direct)
    nunits = max([u for u, _ in units] + [1])
    nmodes = max([b for _, b in units] + [1])

    pin_names_hidden = False
    pn = find(sym, "pin_names")
    if pn is not None and has_flag(pn, "hide"):
        pin_names_hidden = True
    pnum = find(sym, "pin_numbers")
    pin_numbers_hidden = pnum is not None and has_flag(pnum, "hide")

    description = prop("Description", prop("ki_description", ""))
    comp = [("RECORD", 1), ("LibReference", name), ("ComponentDescription", description or None),
            ("PartCount", nunits + 1), ("DisplayModeCount", nmodes), ("IndexInSheet", -1), ("OwnerPartId", -1),
            ("CurrentPartId", 1), ("LibraryPath", "*"), ("SourceLibraryName", "*"), ("SheetPartFileName", "*"),
            ("TargetFileName", "*"), ("UniqueID", uid8()), ("AreaColor", COLOR_AREA), ("Color", COLOR_LINE),
            ("PartIDLocked", "T" if "ki_locked" in props else "F"), ("DesignItemId", name)]
    comp_index = len(records)
    records.append(None)  # uzupelnione na koncu (AllPinCount)
    pin_count = 0

    def owner(part, mode):
        return [("OwnerPartId", part)] + ([("OwnerPartDisplayMode", mode)] if mode else [])

    def emit_items(items, part, mode):
        nonlocal pin_count
        for it in items:
            h = head(it)
            w = stroke_width(it)
            ft = fill_type(it)
            fill = []
            if ft == "outline":
                fill = [("IsSolid", "T"), ("AreaColor", COLOR_LINE)]
            elif ft == "background":
                fill = [("IsSolid", "T"), ("AreaColor", COLOR_AREA)]
            else:
                fill = [("AreaColor", COLOR_AREA)]
            if h == "rectangle":
                x1, y1, _ = xy(it, "start")
                x2, y2, _ = xy(it, "end")
                rec = ([("RECORD", 14)] + owner(part, mode) + sch_pt("Location.X", "Location.Y", min(x1, x2), min(y1, y2))
                       + sch_pt("Corner.X", "Corner.Y", max(x1, x2), max(y1, y2))
                       + [("LineWidth", sch_linewidth(w)), ("Color", COLOR_LINE)] + fill
                       + ([("Transparent", "T")] if ft == "none" else []) + [("UniqueID", uid8())])
                records.append(sch_record(props_record(rec)))
            elif h == "polyline":
                pts = [(float(p[1]), float(p[2])) for p in find(it, "pts")[1:] if head(p) == "xy"]
                filled = ft in ("outline", "background")
                rec = [("RECORD", 7 if filled else 6)] + owner(part, mode)
                rec += [("LineWidth", sch_linewidth(w)), ("Color", COLOR_LINE)]
                if filled:
                    rec += fill
                rec += [("LocationCount", len(pts))]
                for i, (x, y) in enumerate(pts, 1):
                    rec += sch_pt("X%d" % i, "Y%d" % i, x, y)
                rec += [("UniqueID", uid8())]
                records.append(sch_record(props_record(rec)))
            elif h == "circle":
                cx, cy, _ = xy(it, "center")
                r = fval(it, "radius")
                rec = ([("RECORD", 8)] + owner(part, mode) + sch_pt("Location.X", "Location.Y", cx, cy)
                       + sch_coord("Radius", r) + sch_coord("SecondaryRadius", r)
                       + [("LineWidth", sch_linewidth(w)), ("Color", COLOR_LINE)] + fill + [("UniqueID", uid8())])
                records.append(sch_record(props_record(rec)))
            elif h == "arc":
                sx, sy, _ = xy(it, "start")
                ex, ey, _ = xy(it, "end")
                if find(it, "mid") is not None:
                    mx, my, _ = xy(it, "mid")
                    c = arc_from_3pts((sx, sy), (mx, my), (ex, ey))
                    if c is None:
                        warn("%s: zdegenerowany luk pominiety" % name)
                        continue
                    cx, cy, r, a0, a1 = c
                else:  # stary format (radius (at)(length)(angles))
                    rad = find(it, "radius")
                    cx, cy, _ = xy(rad, "at")
                    r = fval(rad, "length")
                    ang = find(rad, "angles")
                    a0, a1 = float(ang[1]), float(ang[2])
                rec = ([("RECORD", 12)] + owner(part, mode) + sch_pt("Location.X", "Location.Y", cx, cy)
                       + sch_coord("Radius", r) + [("LineWidth", sch_linewidth(w)),
                                                   ("StartAngle", "%.3f" % a0), ("EndAngle", "%.3f" % a1),
                                                   ("Color", COLOR_LINE), ("UniqueID", uid8())])
                records.append(sch_record(props_record(rec)))
            elif h == "bezier":
                pts = [(float(p[1]), float(p[2])) for p in find(it, "pts")[1:] if head(p) == "xy"]
                rec = [("RECORD", 5)] + owner(part, mode) + [("LineWidth", sch_linewidth(w)), ("Color", COLOR_LINE),
                                                             ("LocationCount", len(pts))]
                for i, (x, y) in enumerate(pts, 1):
                    rec += sch_pt("X%d" % i, "Y%d" % i, x, y)
                records.append(sch_record(props_record(rec + [("UniqueID", uid8())])))
            elif h == "text":
                x, y, a = xy(it)
                if abs(a) > 360:
                    a /= 10.0
                orient = int(round(a / 90.0)) % 4
                rec = ([("RECORD", 4)] + owner(part, mode) + sch_pt("Location.X", "Location.Y", x, y)
                       + ([("Orientation", orient)] if orient else [])
                       + [("Justification", justification(text_justify(it))), ("Color", COLOR_LINE),
                          ("FontID", fonts.get(text_size(it))), ("Text", it[1]), ("UniqueID", uid8())])
                records.append(sch_record(props_record(rec)))
            elif h == "text_box":
                warn("%s: text_box nieobslugiwany - pominiety" % name)
            elif h == "pin":
                records.append(sch_record(build_pin(it, part, mode, pin_names_hidden, pin_numbers_hidden, name),
                                          binary=True))
                pin_count += 1

    common = []
    for (u, b), subs in sorted(units.items()):
        if u == 0:
            common += [(b, it) for s in subs for it in s[2:] if isinstance(it, list)]
    if common and nunits > 1:
        warn("%s: elementy wspolne (unit 0) zduplikowane do kazdej z %d czesci" % (name, nunits))
    for part in range(1, nunits + 1):
        for mode in range(1, nmodes + 1):
            items = []
            for b, it in common:
                if b == mode or b == 0:
                    items.append(it)
            for s in units.get((part, mode), []):
                items += [it for it in s[2:] if isinstance(it, list)]
            emit_items(items, part, mode - 1)

    # parametry
    ref = props.get("Reference")
    rx, ry, _ = xy(ref) if ref else (0, 0, 0)
    prefix = prop("Reference", "U")
    desig = ([("RECORD", 34), ("IndexInSheet", -1), ("OwnerPartId", -1)] + sch_pt("Location.X", "Location.Y", rx, ry)
             + [("Color", COLOR_DESIG), ("FontID", fonts.get(text_size(ref) if ref else 1.27)), ("Text", prefix + "?"),
                ("Name", "Designator"), ("ReadOnlyState", 1)]
             + ([("IsHidden", "T")] if ref is not None and text_hidden(ref) else []) + [("UniqueID", uid8())])
    records.append(sch_record(props_record(desig)))

    valp = props.get("Value")
    value = prop("Value") or name
    vx, vy, _ = xy(valp) if valp else (0, 0, 0)
    comment = ([("RECORD", 41), ("IndexInSheet", -1), ("OwnerPartId", -1)] + sch_pt("Location.X", "Location.Y", vx, vy)
               + [("Color", COLOR_PARAM), ("FontID", fonts.get(text_size(valp) if valp else 1.27)), ("Text", value),
                  ("Name", "Comment")]
               + ([("IsHidden", "T")] if valp is not None and text_hidden(valp) else []) + [("UniqueID", uid8())])
    records.append(sch_record(props_record(comment)))

    skip = {"Reference", "Value", "Footprint", "Description", "ki_keywords", "ki_fp_filters", "ki_description",
            "ki_locked"}
    for pname, p in props.items():
        if pname in skip or not p[2]:
            continue
        px, py, _ = xy(p)
        altium_name = "ComponentLink1URL" if pname == "Datasheet" else pname
        rec = ([("RECORD", 41), ("IndexInSheet", -1), ("OwnerPartId", -1)] + sch_pt("Location.X", "Location.Y", px, py)
               + [("Color", COLOR_PARAM), ("FontID", fonts.get(text_size(p))), ("Text", p[2]), ("Name", altium_name)]
               + ([("IsHidden", "T")] if text_hidden(p) or pname == "Datasheet" else []) + [("UniqueID", uid8())])
        records.append(sch_record(props_record(rec)))
        if pname == "Datasheet":
            rec = [("RECORD", 41), ("IndexInSheet", -1), ("OwnerPartId", -1), ("Color", COLOR_PARAM), ("FontID", 1),
                   ("IsHidden", "T"), ("Text", "Datasheet"), ("Name", "ComponentLink1Description"),
                   ("UniqueID", uid8())]
            records.append(sch_record(props_record(rec)))
    kw = prop("ki_keywords")
    if kw:
        comp.append(("ComponentKeywords", kw))  # niestandardowe, nieszkodliwe
    # bez podpinania footprintu - symbol z footprintem laczy baza danych

    comp.append(("AllPinCount", pin_count))
    records[comp_index] = sch_record(props_record(comp))
    return name, nunits + 1, description, b"".join(records)


def build_pin(pin, part, mode, names_hidden, numbers_hidden, symname):
    etype = pin[1]
    shape = pin[2] if len(pin) > 2 and not isinstance(pin[2], list) else "line"
    x, y, ang = xy(pin)
    length = fval(pin, "length", 2.54)
    name = kicad_overbar(val(pin, "name", ""))
    number = val(pin, "number", "")
    # KiCad: (at) = koniec elektryczny, kat = kierunek od konca do korpusu
    # Altium: Location = koniec przy korpusie, orientacja = kierunek od korpusu do konca
    rad = math.radians(ang)
    bx, by = x + length * math.cos(rad), y + length * math.sin(rad)
    orient = int(round(((ang + 180) % 360) / 90.0)) % 4

    def unit(v, what):
        u = v / SCH_UNIT
        r = int(round(u))
        if abs(u - r) > 1e-3:
            warn("%s pin %s: %s %.4f mm poza siatka 10 mil - zaokraglono" % (symname, number, what, v))
        return r

    inner = 3 if "clock" in shape else 0
    outer = 1 if shape in ("inverted", "inverted_clock") else (2 if shape in ("input_low", "clock_low") else
                                                                (3 if shape == "output_low" else 0))
    cong = orient | 0x20
    if has_flag(pin, "hide"):
        cong |= 0x04
    if not names_hidden:
        cong |= 0x08
    if not numbers_hidden:
        cong |= 0x10
    b = bytearray(struct.pack("<I", 2))
    b += struct.pack("<BhB", 0, part, mode)
    b += bytes([inner, outer, 0, 0])
    b += pstr("")                     # opis
    b += bytes([1, ELEC.get(etype, 4), cong])
    b += struct.pack("<hhh", unit(length, "dlugosc"), unit(bx, "X"), unit(by, "Y"))
    b += struct.pack("<I", 0)         # kolor
    b += pstr(name) + pstr(number) + pstr("") + pstr("|&|") + pstr("")
    return bytes(b)


def write_schlib(sym_files, path):
    fonts = FontTable()
    comps = []
    for f in sym_files:
        tree = parse_sexpr(open(f, encoding="utf-8").read())
        if head(tree) != "kicad_symbol_lib":
            raise ValueError("%s nie jest biblioteka symboli KiCad" % f)
        for sym in resolve_extends(findall(tree, "symbol")):
            print("  symbol: " + sym[1])
            comps.append(build_sch_component(sym, fonts))

    root = CfbNode("Root Entry")
    hdr = [("HEADER", "Protel for Windows - Schematic Library Editor Binary File Version 5.0"), ("Weight", 27),
           ("MinorVersion", 9), ("UniqueID", uid8()), ("FontIdCount", len(fonts.fonts))]
    for i, (fn, sz) in enumerate(fonts.fonts, 1):
        hdr += [("Size%d" % i, sz), ("FontName%d" % i, fn)]
    hdr += [("UseMBCS", "T"), ("IsBOC", "T"), ("SheetStyle", 9), ("BorderOn", "T"), ("SheetNumberSpaceSize", 12),
            ("AreaColor", 16317695), ("SnapGridOn", "T"), ("SnapGridSize", 10), ("VisibleGridOn", "T"),
            ("VisibleGridSize", 10), ("CustomX", 18000), ("CustomY", 18000), ("UseCustomSheet", "T"),
            ("ReferenceZonesOn", "T"), ("Display_Unit", 0), ("CompCount", len(comps))]
    used = set()
    keys = []
    for i, (name, partcount, descr, data) in enumerate(comps):
        hdr += [("LibRef%d" % i, name), ("CompDescr%d" % i, descr), ("PartCount%d" % i, partcount)]
        on = ole_name(name, used)
        if on != name:
            keys.append((name, on))
        st = root.storage(on)
        st.stream("Data", data)
    root.stream("FileHeader", sch_record(props_record(hdr)))
    root.stream("Storage", sch_record(props_record([("HEADER", "Icon storage")])))
    if keys:
        sk = [("KeyCount", len(keys))]
        for i, (n, k) in enumerate(keys):
            sk += [("LibRef%d" % i, n), ("SectionKey%d" % i, k)]
        root.stream("SectionKeys", sch_record(props_record(sk)))
    write_cfb(root, path, root_clsid=bytes.fromhex("8A44B1F9C1F7F047BF5384BCEC520625"))
    return len(comps)


# --------------------------------------------------------------------------------------------------
# PcbLib
# --------------------------------------------------------------------------------------------------

PCB_UNIT = 1e7 / 25.4  # jednostek wewnetrznych (1/10000 mil) na mm

# Warstwy Altium: nazwa -> (stary ID warstwy, ID V7)
ALTIUM_LAYERS = {
    "Top Layer": (1, 0x01000001), "Bottom Layer": (32, 0x0100FFFF),
    "Top Overlay": (33, 0x01030006), "Bottom Overlay": (34, 0x01030007),
    "Top Paste": (35, 0x01030008), "Bottom Paste": (36, 0x01030009),
    "Top Solder": (37, 0x0103000A), "Bottom Solder": (38, 0x0103000B),
    "Drill Guide": (55, 0x0103000C), "Keep-Out Layer": (56, 0x0103000D), "Drill Drawing": (73, 0x0103000E),
}
for _i in range(1, 31):
    ALTIUM_LAYERS["Mid-Layer %d" % _i] = (1 + _i, 0x01000001 + _i)
for _i in range(1, 33):
    # warstwy Mech 17+ nie maja starego ID - Altium zapisuje 72 (Mech16), liczy sie ID V7
    ALTIUM_LAYERS["Mechanical %d" % _i] = (56 + min(_i, 16), 0x01020000 + _i)
ALTIUM_LAYERS["Top Assembly"] = ALTIUM_LAYERS["Mechanical 1"]      # nazwy z naglowka oryginalnego pliku
ALTIUM_LAYERS["Bottom Assembly"] = ALTIUM_LAYERS["Mechanical 2"]

# Tlumaczenie warstw KiCad -> Altium wg natywnego pliku BGA96C80P9X16_900X1300X120.PcbLib:
# F.Fab -> Mechanical 15, F.CrtYd -> Mechanical 20. Pozostale warstwy mechaniczne dobrane tak, by nie kolidowaly.
# Mozna nadpisac plikiem JSON (--layer-map), np. {"F.Fab": "Top Assembly"}.
KICAD_TO_ALTIUM = {
    "F.Cu": "Top Layer", "B.Cu": "Bottom Layer",
    "F.SilkS": "Top Overlay", "B.SilkS": "Bottom Overlay",
    "F.Paste": "Top Paste", "B.Paste": "Bottom Paste",
    "F.Mask": "Top Solder", "B.Mask": "Bottom Solder",
    "F.Fab": "Mechanical 15", "F.CrtYd": "Mechanical 20",
    "B.Fab": "Mechanical 16", "B.CrtYd": "Mechanical 21",
    "Edge.Cuts": "Keep-Out Layer",
    "Dwgs.User": "Mechanical 3", "Cmts.User": "Mechanical 4", "Eco1.User": "Mechanical 5",
    "Eco2.User": "Mechanical 6", "Margin": "Mechanical 7", "F.Adhes": "Mechanical 8", "B.Adhes": "Mechanical 9",
}
for _i in range(1, 31):
    KICAD_TO_ALTIUM["In%d.Cu" % _i] = "Mid-Layer %d" % _i
for _i in range(1, 10):
    KICAD_TO_ALTIUM["User.%d" % _i] = "Mechanical %d" % (21 + _i)
USED_V7_LAYERS = set()
MULTI_LAYER = 74
LAYER_ALIASES = {"F.Silkscreen": "F.SilkS", "B.Silkscreen": "B.SilkS", "F.Courtyard": "F.CrtYd",
                 "B.Courtyard": "B.CrtYd", "F.Fabrication": "F.Fab", "B.Fabrication": "B.Fab",
                 "F.Adhesive": "F.Adhes", "B.Adhesive": "B.Adhes", "User.Drawings": "Dwgs.User",
                 "User.Comments": "Cmts.User", "User.Eco1": "Eco1.User", "User.Eco2": "Eco2.User"}


def pu(mm):
    return int(round(mm * PCB_UNIT))


def layer_of(node, fpname):
    ln = val(node, "layer")
    ln = LAYER_ALIASES.get(ln, ln)
    alt = KICAD_TO_ALTIUM.get(ln)
    if alt not in ALTIUM_LAYERS:
        warn("%s: warstwa %s nieobslugiwana - element pominiety" % (fpname, ln))
        return None
    layer = ALTIUM_LAYERS[alt]
    USED_V7_LAYERS.add(layer[1])
    return layer


def load_layer_map(path):
    import json
    with open(path, encoding="utf-8") as f:
        m = json.load(f)
    for k, v in m.items():
        if v not in ALTIUM_LAYERS:
            raise ValueError("Nieznana warstwa Altium '%s' (dla %s). Dostepne: %s"
                             % (v, k, ", ".join(sorted(ALTIUM_LAYERS))))
        KICAD_TO_ALTIUM[LAYER_ALIASES.get(k, k)] = v


def enable_mech_layers(props):
    """Wlacza w naglowku biblioteki warstwy mechaniczne, na ktorych leza prymitywy."""
    for v7 in USED_V7_LAYERS:
        if v7 >> 16 != 0x0102:
            continue
        n = v7 & 0xFFFF
        if n <= 16:
            props = props.replace("|LAYER%dMECHENABLED=FALSE" % (56 + n), "|LAYER%dMECHENABLED=TRUE" % (56 + n))
        m = re.search(r'\|V9_CACHE_LAYER(\d+)_LAYERID=%d\|' % v7, props)
        if m:
            k = m.group(1)
            props = props.replace("|V9_CACHE_LAYER%s_MECHENABLED=FALSE" % k, "|V9_CACHE_LAYER%s_MECHENABLED=TRUE" % k)
            props = props.replace("|V9_CACHE_LAYER%s_USEDBYPRIMS=FALSE" % k, "|V9_CACHE_LAYER%s_USEDBYPRIMS=TRUE" % k)
    return props


def prim_head(layer, flags=0x0C):
    return bytes([layer]) + struct.pack("<H", flags) + b"\xff" * 10


def pcb_track(layer, x1, y1, x2, y2, w):
    b = prim_head(layer[0])
    b += struct.pack("<iiiii", pu(x1), pu(-y1), pu(x2), pu(-y2), pu(w))
    b += b"\0" * 8
    b += struct.pack("<I", layer[1]) + b"\0" * 4
    assert len(b) == 49
    return b"\x04" + struct.pack("<I", len(b)) + b


def pcb_arc(layer, cx, cy, r, a0, a1, w):
    """cx, cy w ukladzie Altium (y w gore), katy w stopniach CCW."""
    b = prim_head(layer[0])
    end = a1 % 360
    if end == 0 and a1:
        end = 360.0  # pelny okrag: 0 -> 360
    b += struct.pack("<iiiddi", pu(cx), pu(cy), pu(r), a0 % 360, end, pu(w))
    b += b"\0" * 7
    b += struct.pack("<I", layer[1]) + b"\0" * 4
    assert len(b) == 60
    return b"\x01" + struct.pack("<I", len(b)) + b


def pcb_text(layer, x, y, height, rot, width, mirrored, text, ws_index):
    b = bytearray(tpl.TEXT_RECORD)
    b[0] = layer[0]
    struct.pack_into("<iii", b, 13, pu(x), pu(y), pu(height))
    struct.pack_into("<d", b, 27, rot)
    b[35] = 1 if mirrored else 0
    struct.pack_into("<i", b, 36, pu(width))
    struct.pack_into("<I", b, 113, ws_index)
    struct.pack_into("<I", b, 226, layer[1])
    struct.pack_into("<ii", b, 244, pu(x), pu(y))
    t = enc(text)[:255]
    s2 = bytes([len(t)]) + t
    return b"\x05" + struct.pack("<I", len(b)) + bytes(b) + struct.pack("<I", len(s2)) + s2


PAD_ROUND, PAD_RECT, PAD_OCT, PAD_ROUNDRECT = 1, 2, 3, 9


def size_and_shape(shape_alt, corner_pct, hole_shape=0, slot_len=0, slot_rot=0.0, hole_off=(0, 0),
                   size=(0, 0), shape=PAD_RECT):
    b = bytearray()
    b += struct.pack("<29i", *([size[0]] * 29))
    b += struct.pack("<29i", *([size[1]] * 29))
    b += bytes([shape] * 29)
    b += b"\0"
    b += bytes([hole_shape])
    b += struct.pack("<i", slot_len)
    b += struct.pack("<d", slot_rot)
    b += struct.pack("<32i", *([hole_off[0]] * 32))
    b += struct.pack("<32i", *([hole_off[1]] * 32))
    b += b"\0"
    b += bytes([shape_alt] * 32)
    b += bytes([corner_pct] * 32)
    assert len(b) == 596
    return bytes(b)


def pcb_pad(pad, fpname):
    number = pad[1] if len(pad) > 1 else ""
    ptype = pad[2]
    pshape = pad[3]
    x, y, rot = xy(pad)
    sw, sh = fval(pad, "size", 0, 1), fval(pad, "size", 0, 2)
    layers = set()
    lnode = find(pad, "layers")
    for ln in (lnode[1:] if lnode else []):
        layers.add(LAYER_ALIASES.get(ln, ln))
    drill = find(pad, "drill")
    hole = 0.0
    slot = None
    hole_off = (0.0, 0.0)
    if drill is not None:
        args = [a for a in drill[1:] if not isinstance(a, list)]
        if args and args[0] == "oval":
            dw, dh = float(args[1]), float(args[2]) if len(args) > 2 else float(args[1])
            hole = min(dw, dh)
            if abs(dw - dh) > 1e-6:
                slot = (max(dw, dh), 90.0 if dh > dw else 0.0)
        elif args:
            hole = float(args[0])
        off = find(drill, "offset")
        if off is not None:
            hole_off = (float(off[1]), float(off[2]))
            warn("%s pad %s: offset otworu - zapisany w rekordzie rozszerzonym (niezweryfikowane)" % (fpname, number))

    b = bytearray(tpl.PAD_RECORD)
    tht = ptype in ("thru_hole", "np_thru_hole")
    if tht:
        layer = MULTI_LAYER
    elif "B.Cu" in layers and "F.Cu" not in layers:
        layer = 32
    elif "F.Cu" in layers or "*.Cu" in layers:
        layer = 1
    else:
        warn("%s pad %s: pad bez miedzi (%s) - pominiety" % (fpname, number, " ".join(sorted(layers))))
        return None
    flags = 0x0C
    side_f = layer != 32
    if tht:
        if "F.Mask" not in layers and "*.Mask" not in layers:
            flags |= 0x20
        if "B.Mask" not in layers and "*.Mask" not in layers:
            flags |= 0x40
    elif side_f and "F.Mask" not in layers:
        flags |= 0x20
    elif not side_f and "B.Mask" not in layers:
        flags |= 0x40
    b[0] = layer
    struct.pack_into("<H", b, 1, flags)

    shape = {"rect": PAD_RECT, "circle": PAD_ROUND, "oval": PAD_ROUND, "roundrect": PAD_RECT,
             "trapezoid": PAD_RECT, "custom": PAD_RECT}.get(pshape, PAD_RECT)
    if pshape == "custom":
        opts = find(pad, "options")
        anchor = val(opts, "anchor", "rect") if opts else "rect"
        shape = PAD_ROUND if anchor == "circle" else PAD_RECT
        warn("%s pad %s: pad custom - zapisano tylko kotwice (%s)" % (fpname, number, anchor))
    if pshape == "trapezoid":
        warn("%s pad %s: trapezoid zamieniony na prostokat" % (fpname, number))
    corner = 0
    if pshape == "roundrect":
        ratio = fval(pad, "roundrect_rratio", 0.25)
        corner = max(0, min(100, int(round(ratio * 200))))
        if find(pad, "chamfer_ratio") is not None:
            warn("%s pad %s: fazowanie (chamfer) pominiete" % (fpname, number))
    if pshape == "circle":
        sh = sw

    struct.pack_into("<ii", b, 13, pu(x), pu(-y))
    for off in (21, 29, 37):
        struct.pack_into("<ii", b, off, pu(sw), pu(sh))
    struct.pack_into("<i", b, 45, pu(hole))
    b[49] = b[50] = b[51] = shape
    struct.pack_into("<d", b, 52, rot % 360)
    b[60] = 1 if ptype == "thru_hole" else 0   # natywny Altium: pady SMD maja plated=0
    if tht:
        b[114], b[117] = 32, 1

    # maski: domyslnie z regul (szablon ma reczne 4 mil - zerujemy), recznie tylko jesli zdefiniowane w KiCad
    struct.pack_into("<i", b, 86, 0)
    struct.pack_into("<i", b, 90, 0)
    struct.pack_into("<i", b, 121, 0)
    b[101] = b[102] = 0
    smm = find(pad, "solder_mask_margin")
    if smm is not None:
        struct.pack_into("<i", b, 90, pu(float(smm[1])))
        struct.pack_into("<i", b, 121, pu(float(smm[1])))
        b[102] = 1
    psm = find(pad, "solder_paste_margin")
    if psm is not None:
        struct.pack_into("<i", b, 86, pu(float(psm[1])))
        b[101] = 1
    if not tht and ("F.Paste" if side_f else "B.Paste") not in layers:
        # pad bez pasty - ujemna ekspansja wieksza niz pad
        struct.pack_into("<i", b, 86, -pu(max(sw, sh)))
        b[101] = 1

    ext = b""
    if corner or slot or hole_off != (0.0, 0.0):
        ext = size_and_shape(PAD_ROUNDRECT if corner else shape, corner,
                             hole_shape=2 if slot else 0,
                             slot_len=pu(slot[0]) if slot else 0, slot_rot=slot[1] if slot else 0.0,
                             hole_off=(pu(hole_off[0]), pu(-hole_off[1])), size=(pu(sw), pu(sh)), shape=shape)

    name = enc(number)[:255]
    subs = [bytes([len(name)]) + name, b"\0", b"\x04|&|0", b"\0", bytes(b), ext]
    return b"\x02" + b"".join(struct.pack("<I", len(s)) + s for s in subs)


def arc_from_3pts(p1, p2, p3):
    """Zwraca (cx, cy, r, start, end) dla luku CCW przez 3 punkty (uklad y w gore)."""
    (x1, y1), (x2, y2), (x3, y3) = p1, p2, p3
    d = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))
    if abs(d) < 1e-12:
        return None
    ux = ((x1 ** 2 + y1 ** 2) * (y2 - y3) + (x2 ** 2 + y2 ** 2) * (y3 - y1) + (x3 ** 2 + y3 ** 2) * (y1 - y2)) / d
    uy = ((x1 ** 2 + y1 ** 2) * (x3 - x2) + (x2 ** 2 + y2 ** 2) * (x1 - x3) + (x3 ** 2 + y3 ** 2) * (x2 - x1)) / d
    r = math.hypot(x1 - ux, y1 - uy)
    a1 = math.degrees(math.atan2(y1 - uy, x1 - ux))
    a3 = math.degrees(math.atan2(y3 - uy, x3 - ux))
    cross = (x2 - x1) * (y3 - y1) - (y2 - y1) * (x3 - x1)
    if cross > 0:   # p1->p2->p3 przeciwnie do wskazowek zegara
        return ux, uy, r, a1 % 360, a3 % 360
    return ux, uy, r, a3 % 360, a1 % 360


def kicad_text_to_altium(t):
    t = t.replace("${REFERENCE}", ".Designator").replace("%R", ".Designator")
    t = t.replace("${VALUE}", ".Comment").replace("%V", ".Comment")
    return t


def build_footprint(tree, fpname):
    prims = []
    texts = []
    pad_count = 0
    descr = val(tree, "descr", "") or ""

    def outline(layer, pts, w):
        for (ax, ay), (bx, by) in zip(pts, pts[1:] + pts[:1]):
            prims.append(pcb_track(layer, ax, ay, bx, by, w))

    for it in tree[1:]:
        h = head(it)
        if h in ("fp_line", "fp_rect", "fp_circle", "fp_arc", "fp_poly", "fp_text", "property", "pad"):
            pass
        else:
            if h in ("fp_curve", "fp_text_box", "zone", "group", "dimension", "image"):
                warn("%s: %s nieobslugiwany - pominiety" % (fpname, h))
            continue
        if h == "pad":
            p = pcb_pad(it, fpname)
            if p:
                prims.append(p)
                pad_count += 1
            continue
        layer = layer_of(it, fpname)
        if layer is None:
            continue
        w = stroke_width(it)
        if h == "fp_line":
            x1, y1, _ = xy(it, "start")
            x2, y2, _ = xy(it, "end")
            prims.append(pcb_track(layer, x1, y1, x2, y2, w))
        elif h == "fp_rect":
            x1, y1, _ = xy(it, "start")
            x2, y2, _ = xy(it, "end")
            outline(layer, [(x1, y1), (x2, y1), (x2, y2), (x1, y2)], w)
            if fill_type(it) == "solid":
                warn("%s: wypelniony fp_rect zapisany jako kontur" % fpname)
        elif h == "fp_poly":
            pts = [(float(p[1]), float(p[2])) for p in find(it, "pts")[1:] if head(p) == "xy"]
            if len(pts) >= 2:
                outline(layer, pts, w if w > 0 else 0.1)
            if fill_type(it) == "solid":
                warn("%s: wypelniony fp_poly zapisany jako kontur" % fpname)
        elif h == "fp_circle":
            cx, cy, _ = xy(it, "center")
            ex, ey, _ = xy(it, "end")
            r = math.hypot(ex - cx, ey - cy)
            if fill_type(it) == "solid":
                outer = r + w / 2
                prims.append(pcb_arc(layer, cx, -cy, outer / 2, 0, 360, outer))
            else:
                prims.append(pcb_arc(layer, cx, -cy, r, 0, 360, w))
        elif h == "fp_arc":
            sx, sy, _ = xy(it, "start")
            ex, ey, _ = xy(it, "end")
            if find(it, "mid") is not None:
                mx, my, _ = xy(it, "mid")
                p1, p2, p3 = (sx, sy), (mx, my), (ex, ey)
            else:
                # format <= v5: start = srodek, end = punkt poczatkowy, angle = rozpietosc (zgodnie z ruchem
                # wskazowek zegara na ekranie, czyli dodatnio w ukladzie y-w-dol)
                ang = math.radians(fval(it, "angle"))
                dx, dy = ex - sx, ey - sy

                def rot(a):
                    return sx + dx * math.cos(a) - dy * math.sin(a), sy + dx * math.sin(a) + dy * math.cos(a)
                p1, p2, p3 = (ex, ey), rot(ang / 2), rot(ang)
            c = arc_from_3pts((p1[0], -p1[1]), (p2[0], -p2[1]), (p3[0], -p3[1]))
            if c is None:
                prims.append(pcb_track(layer, p1[0], p1[1], p3[0], p3[1], w))
            else:
                cx, cy, r, a0, a1 = c
                prims.append(pcb_arc(layer, cx, cy, r, a0, a1, w))
        elif h in ("fp_text", "property"):
            if h == "fp_text":
                kind, txt = it[1], it[2]
            else:
                kind, txt = {"Reference": "reference", "Value": "value"}.get(it[1], "prop"), it[2]
                if kind == "prop":
                    continue
            if kind == "reference" or text_hidden(it):
                continue  # Altium rysuje desygnator sam
            txt = kicad_text_to_altium(txt) if kind == "user" else ".Comment"
            x, y, rot = xy(it)
            height = text_size(it)
            eff = find(it, "effects")
            font = find(eff, "font") if eff else None
            thick = fval(font, "thickness", height * 0.15) if font else height * 0.15
            mirrored = "mirror" in text_justify(it) or layer[0] in (34, 32)
            # KiCad: srodek tekstu; Altium: lewy dolny rog -> przyblizenie szerokosci czcionki kreskowej
            tw = len(txt) * height * 0.745
            th = height + 2 * thick
            ra = math.radians(rot)
            dx, dy = -tw / 2, -th / 2
            ox = x * 1 + dx * math.cos(ra) - dy * math.sin(ra)
            oy = -y + dx * math.sin(ra) + dy * math.cos(ra)
            texts.append(pcb_text(layer, ox, oy, height, rot % 360, thick, mirrored, txt, len(texts)))
    # kolejnosc jak w importerze Altium: teksty, grafika, pady
    ordered = texts + [p for p in prims if p[0] != 2] + [p for p in prims if p[0] == 2]
    count = len(ordered)
    return ordered, count, pad_count, descr


def write_pcblib(fp_files, path):
    root = CfbNode("Root Entry")
    used = set()
    comps = []
    for f in fp_files:
        tree = parse_sexpr(open(f, encoding="utf-8").read())
        if head(tree) not in ("module", "footprint"):
            raise ValueError("%s nie jest footprintem KiCad" % f)
        name = tree[1]
        print("  footprint: " + name)
        prims, count, pads, descr = build_footprint(tree, name)
        on = ole_name(name, used)
        st = root.storage(on)
        st.stream("Header", struct.pack("<I", count))
        nm = enc(name)[:255]
        st.stream("Data", struct.pack("<I", len(nm) + 1) + bytes([len(nm)]) + nm + b"".join(prims))
        par = props_record([("PATTERN", name), ("HEIGHT", "0mil"), ("DESCRIPTION", descr), ("ITEMGUID", ""),
                            ("REVISIONGUID", "")])
        st.stream("Parameters", struct.pack("<I", len(par)) + par)
        ws = bytearray()
        for i, p in enumerate(t for t in prims if t[0] == 5):
            ln = struct.unpack_from("<I", p, 1)[0]
            txt = p[1 + 4 + ln + 4 + 1:].decode("cp1252")
            ws += ("|ENCODEDTEXT%d=" % i + ",".join(str(ord(c)) for c in txt)).encode("ascii")
        ws += b"\0"
        st.stream("WideStrings", struct.pack("<I", len(ws)) + ws)
        comps.append((name, on, pads, descr))

    if any(n != o for n, o, _, _ in comps):
        warn("nazwy footprintow > 31 znakow - zapisano SectionKeys (format niezweryfikowany)")
        sk = struct.pack("<I", len([c for c in comps if c[0] != c[1]]))
        for n, o, _, _ in comps:
            if n != o:
                nb, ob = enc(n), enc(o)
                sk += struct.pack("<I", len(nb) + 1) + bytes([len(nb)]) + nb + struct.pack("<I", len(ob)) + ob
        root.stream("SectionKeys", sk)

    now = datetime.datetime.now()
    props = tpl.LIBRARY_HEADER_PROPS.decode("latin1")
    props = enable_mech_layers(props.replace("|FILENAME=", "|FILENAME=" + os.path.abspath(path), 1))
    props = re.sub(r'\|DATE=[^|]*', "|DATE=" + now.strftime("%d.%m.%Y"), props, count=1)
    props = re.sub(r'\|TIME=[^|]*', "|TIME=" + now.strftime("%H:%M:%S"), props, count=1)
    pb = props.encode("latin1") + b"\0"
    data = struct.pack("<I", len(pb)) + pb + struct.pack("<I", len(comps))
    for n, _, _, _ in comps:
        nb = enc(n)[:255]
        data += struct.pack("<I", len(nb) + 1) + bytes([len(nb)]) + nb

    lib = root.storage("Library")
    lib.stream("Header", struct.pack("<I", 1))
    lib.stream("Data", data)
    lib.stream("EmbeddedFonts", struct.pack("<I", 0))
    toc = "".join("Name=%s|Pad Count=%d|Height=0|Description=%s\r\n" % (n, p, d) for n, _, p, d in comps)
    tb = enc(toc) + b"\0"
    s = lib.storage("ComponentParamsTOC")
    s.stream("Header", struct.pack("<I", 1))
    s.stream("Data", struct.pack("<I", len(tb)) + tb)
    s = lib.storage("LayerKindMapping")
    s.stream("Header", struct.pack("<I", 1))
    s.stream("Data", tpl.LAYER_KIND_MAPPING)
    for nm in ("Models", "ModelsNoEmbed", "Textures"):
        s = lib.storage(nm)
        s.stream("Header", struct.pack("<I", 0))
        s.stream("Data", b"")
    pv = props_record([("PADVIALIBRARY.LIBRARYID", "{1C413151-6F78-4AB8-BB41-60AED2378F31}"),
                       ("PADVIALIBRARY.LIBRARYNAME", "<Local>"), ("PADVIALIBRARY.DISPLAYUNITS", 1)])
    s = lib.storage("PadViaLibrary")
    s.stream("Header", struct.pack("<I", 0))
    s.stream("Data", struct.pack("<I", len(pv)) + pv)
    fv = root.storage("FileVersionInfo")
    fv.stream("Header", struct.pack("<I", 1))
    fv.stream("Data", tpl.FILE_VERSION_INFO)
    root.stream("FileHeader", tpl.PCB_FILE_HEADER_PREFIX + b"\x08" + uid8().encode())
    write_cfb(root, path)
    return [c[0] for c in comps]


# --------------------------------------------------------------------------------------------------
# Dump (diagnostyka, wymaga olefile)
# --------------------------------------------------------------------------------------------------

def dump(path):
    import olefile
    o = olefile.OleFileIO(path)
    for e in o.listdir():
        p = "/".join(e)
        d = o.openstream(p).read()
        print("=== %s (%d B)" % (p, len(d)))
        if path.lower().endswith(".schlib") and (e[-1] in ("Data", "FileHeader", "Storage", "SectionKeys")):
            i = 0
            while i + 4 <= len(d):
                n = struct.unpack_from("<I", d, i)[0]
                ln, typ = n & 0xFFFFFF, n >> 24
                rec = d[i + 4:i + 4 + ln]
                print("  [bin] " + rec.hex(" ") if typ else "  " + rec.rstrip(b"\0").decode("cp1252"))
                i += 4 + ln
        elif len(d) < 400:
            print("  ", d)


# --------------------------------------------------------------------------------------------------

def expand(paths, ext):
    out = []
    for p in paths or []:
        if os.path.isdir(p):
            out += sorted(os.path.join(p, f) for f in os.listdir(p) if f.endswith(ext))
        else:
            out.append(p)
    return out


def main():
    ap = argparse.ArgumentParser(description="Konwerter bibliotek KiCad -> Altium (SchLib/PcbLib)")
    ap.add_argument("--sym", nargs="*", help="pliki .kicad_sym")
    ap.add_argument("--fp", nargs="*", help="pliki .kicad_mod lub katalogi .pretty")
    ap.add_argument("-o", "--out", default="altium_out", help="katalog wyjsciowy")
    ap.add_argument("--name", help="nazwa bazowa bibliotek wyjsciowych")
    ap.add_argument("--layer-map", help='plik JSON z nadpisaniem tlumaczenia warstw, np. {"F.Fab": "Top Assembly"}')
    ap.add_argument("--dump", help="wypisz zawartosc pliku Altium (.SchLib/.PcbLib)")
    a = ap.parse_args()
    if a.dump:
        dump(a.dump)
        return
    if a.layer_map:
        load_layer_map(a.layer_map)
    syms = expand(a.sym, ".kicad_sym")
    fps = expand(a.fp, ".kicad_mod")
    if not syms and not fps:
        ap.error("podaj --sym i/lub --fp")
    os.makedirs(a.out, exist_ok=True)
    base = a.name or os.path.splitext(os.path.basename((syms or fps)[0]))[0]
    if fps:
        out = os.path.join(a.out, base + ".PcbLib")
        print("PcbLib -> " + out)
        write_pcblib(fps, out)
    if syms:
        out = os.path.join(a.out, base + ".SchLib")
        print("SchLib -> " + out)
        write_schlib(syms, out)
    print("Gotowe. Ostrzezen: %d" % len(WARNINGS))


if __name__ == "__main__":
    main()
