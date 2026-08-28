"""Benchmark matrix: leptris vs lxml vs ElementTree vs minidom.

Python twin of leptris-ruby's leptris_vs_nokogiri.rb — same fixtures,
same iteration counts, so the two matrices are comparable.

Run:  python -m benchmarks.matrix   (LEPTRIS_LIB_PATH must be set)
Missing libraries degrade to skipped rows; unsupported operations
carry a reason. Losses are results — nothing is muted.
"""

from __future__ import annotations

import gc
import json
import os
import platform
import sys
import time
from pathlib import Path

SMALL = (
    "<catalog>"
    + "".join(
        f"<book id='{i}'><title>Book {i}</title></book>" for i in range(1, 11)
    )
    + "</catalog>"
)

MEDIUM = (
    "<catalog version='2.0'>"
    + "".join(
        f"<book id='{i}' lang='en'>"
        f"<title>Book {i}</title>"
        f"<author id='a{i}'>Author {i}</author>"
        f"<price currency='USD'>{i}.99</price>"
        f"</book>"
        for i in range(1, 101)
    )
    + "</catalog>"
)

N_PARSE_SMALL = 5_000
N_PARSE_MEDIUM = 1_000
N_QUERY = 10_000
N_TRAVERSE = 2_000
N_SERIALIZE = 1_000


def _leptris_libs():
    import leptris
    from leptris import libleptris_version

    pinned = "unknown"
    pin_file = Path(__file__).resolve().parent.parent / "libleptris-version.txt"
    if pin_file.exists():
        pinned = pin_file.read_text().strip()
    return {
        "leptris": leptris.__version__,
        "libleptris": libleptris_version() or "unknown",
        "libleptris pin": pinned,
    }


def _loadavg():
    """1-minute load average, or None where unavailable (Windows)."""
    try:
        return round(os.getloadavg()[0], 2)
    except (AttributeError, OSError):
        return None


def _contended(loadavg):
    """Timings recorded above 2x the CPU count are machine noise."""
    if loadavg is None:
        return False
    try:
        cpus = os.cpu_count() or 1
    except AttributeError:
        return False
    return loadavg > 2 * cpus


def _make_benchmarks():
    """Returns {lib_name: {op_name: callable}} plus skip metadata."""
    benchmarks = {}
    skips = {}

    # leptris ---------------------------------------------------------
    try:
        from leptris import Document, tostring

        def parse_small():
            with Document.parse(SMALL):
                pass

        def parse_medium():
            with Document.parse(MEDIUM):
                pass

        doc = Document.parse(MEDIUM)
        root = doc.getroot()

        benchmarks["leptris"] = {
            "parse small": parse_small,
            "parse medium": parse_medium,
            "xpath count(//book)": lambda: doc.xpath("count(//book)"),
            "xpath //book": lambda: doc.xpath("//book"),
            "xpath //book[@id='50']": lambda: doc.xpath("//book[@id='50']"),
            "xpath //book[price > 50]": lambda: doc.xpath("//book[price > 50]"),
            "xpath //author | //title": lambda: doc.xpath("//author | //title"),
            "xpath //book[@id=$id]": lambda: doc.xpath(
                "//book[@id=$id]", variables={"id": "50"}
            ),
            "traversal": _traverse_iter(root.iter),
            "serialize": lambda: tostring(doc),
        }
    except ImportError as error:
        skips["leptris"] = str(error)

    # lxml ------------------------------------------------------------
    try:
        import lxml.etree as etree

        lroot = etree.fromstring(MEDIUM.encode())

        benchmarks["lxml"] = {
            "parse small": lambda: etree.fromstring(SMALL.encode()),
            "parse medium": lambda: etree.fromstring(MEDIUM.encode()),
            "xpath count(//book)": lambda: lroot.xpath("count(//book)"),
            "xpath //book": lambda: lroot.xpath("//book"),
            "xpath //book[@id='50']": lambda: lroot.xpath("//book[@id='50']"),
            "xpath //book[price > 50]": lambda: lroot.xpath("//book[price > 50]"),
            "xpath //author | //title": lambda: lroot.xpath("//author | //title"),
            "xpath //book[@id=$id]": lambda: lroot.xpath("//book[@id=$id]", id="50"),
            "traversal": _traverse_iter(lroot.iter),
            "serialize": lambda: etree.tostring(lroot),
        }
    except ImportError as error:
        skips["lxml"] = str(error)

    # ElementTree -----------------------------------------------------
    try:
        import xml.etree.ElementTree as ET

        eroot = ET.fromstring(MEDIUM)

        benchmarks["ElementTree"] = {
            "parse small": lambda: ET.fromstring(SMALL),
            "parse medium": lambda: ET.fromstring(MEDIUM),
            "xpath count(//book)": None,
            "xpath //book": lambda: eroot.findall(".//book"),
            "xpath //book[@id='50']": lambda: eroot.findall(".//book[@id='50']"),
            "xpath //book[price > 50]": None,
            "xpath //author | //title": None,
            "traversal": _traverse_iter(eroot.iter),
            "serialize": lambda: ET.tostring(eroot),
        }
    except ImportError as error:
        skips["ElementTree"] = str(error)

    # minidom ---------------------------------------------------------
    try:
        from xml.dom import minidom

        mdom = minidom.parseString(MEDIUM)

        def walk(node):
            for child in node.childNodes:
                walk(child)

        benchmarks["minidom"] = {
            "parse small": lambda: minidom.parseString(SMALL),
            "parse medium": lambda: minidom.parseString(MEDIUM),
            "xpath count(//book)": None,
            "xpath //book": None,
            "xpath //book[@id='50']": None,
            "xpath //book[price > 50]": None,
            "xpath //author | //title": None,
            "traversal": lambda: walk(mdom.documentElement),
            "serialize": lambda: mdom.toxml(),
        }
    except ImportError as error:
        skips["minidom"] = str(error)

    return benchmarks, skips


def _traverse_iter(factory):
    def run():
        for _ in factory():
            pass

    return run


def _time_op(fn, iterations):
    for _ in range(max(1, iterations // 10)):
        fn()  # warmup: dlopen, code-signature checks, caches
    gc.collect()
    start = time.perf_counter()
    for _ in range(iterations):
        fn()
    elapsed = time.perf_counter() - start
    return elapsed / iterations * 1_000_000


OPERATIONS = [
    ("parse small", N_PARSE_SMALL),
    ("parse medium", N_PARSE_MEDIUM),
    ("xpath count(//book)", N_QUERY),
    ("xpath //book", N_QUERY),
    ("xpath //book[@id='50']", N_QUERY),
    ("xpath //book[price > 50]", N_QUERY),
    ("xpath //author | //title", N_QUERY),
    ("xpath //book[@id=$id]", N_QUERY),
    ("traversal", N_TRAVERSE),
    ("serialize", N_SERIALIZE),
]

LIB_ORDER = ["leptris", "lxml", "ElementTree", "minidom"]


def main():
    benchmarks, skips = _make_benchmarks()

    versions = {}
    try:
        versions.update(_leptris_libs())
    except ImportError as error:
        versions["leptris"] = f"unavailable ({error})"
    try:
        import lxml.etree as etree

        versions["lxml"] = etree.__version__
    except ImportError:
        versions["lxml"] = "not installed"
    versions["ElementTree"] = sys.version.split()[0]
    versions["minidom"] = "stdlib"

    loadavg = _loadavg()
    contended = _contended(loadavg)
    print(f"python {sys.version.split()[0]} on {platform.platform()}")
    print(
        f"  loadavg {loadavg} — "
        + ("CONTENDED: timings are unreliable, do not record"
           if contended else "quiet")
    )
    for name in LIB_ORDER:
        print(f"  {name:<13} {versions.get(name, '?')}")
    print()

    results = []
    table_rows = []
    for op, iterations in OPERATIONS:
        row = {"op": op}
        timings = {}
        for lib in LIB_ORDER:
            if lib not in benchmarks:
                results.append({"lib": lib, "op": op, "skipped": skips[lib]})
                row[lib] = "skip"
                continue
            fn = benchmarks[lib][op]
            if fn is None:
                reason = "XPath subset" if lib == "ElementTree" else "no XPath"
                results.append({"lib": lib, "op": op, "skipped": reason})
                row[lib] = f"skip ({reason})"
                continue
            us = _time_op(fn, iterations)
            results.append({"lib": lib, "op": op, "us": round(us, 2)})
            row[lib] = f"{us:8.2f}"
            timings[lib] = us
        row["winner"] = min(timings, key=timings.get) if timings else "—"
        table_rows.append(row)
        print(f"  {op:<26} " + "  ".join(
            f"{lib}: {row.get(lib, '?')}" for lib in LIB_ORDER
        ))
    print()

    suffix = " (CONTENDED)" if contended else ""
    display = {"op": "operation", "winner": "winner" + suffix,
               **{lib: lib for lib in LIB_ORDER}}
    keys = ["op"] + LIB_ORDER + ["winner"]
    widths = [max(len(display[k]), *(len(str(row[k])) for row in table_rows)) for k in keys]
    print("| " + " | ".join(display[k].ljust(w) for k, w in zip(keys, widths)) + " |")
    print("|" + "|".join("-" * (w + 2) for w in widths) + "|")
    for row in table_rows:
        print("| " + " | ".join(str(row[k]).ljust(w) for k, w in zip(keys, widths)) + " |")
    print()

    print("--- results json ---")
    print(json.dumps({
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "loadavg": loadavg,
        "contended": contended,
        "libs": versions,
        "results": results,
    }, indent=2))


if __name__ == "__main__":
    main()
