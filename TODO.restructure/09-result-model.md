**STATUS: DONE 2026-09-07 — `leptris/_results.py` owns nodeset/scalar conversion; `xquery.py` no longer reaches into `xpath.py` privates (layering fixed); `_XPathEngine._convert` delegates for compatibility.**

# 09 — Extract the shared result model (P1)

## Problem
Result conversion (nodeset wrapping, scalar conversion) lived as
private statics on `_XPathEngine`, and `xquery.py` imported that
private class across modules — a layering violation: conversion is
not an XPath concern, it is the binding's result MODEL, shared by
every evaluation surface.

## Plan
`leptris/_results.py` with module-level `convert`/`nodeset`;
engines import it; `_XPathEngine._convert` kept as a one-line
delegate (public-ish compatibility for anything reaching it).

## Acceptance
Both engines route through one conversion module; suite green.
