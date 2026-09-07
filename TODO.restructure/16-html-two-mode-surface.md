**STATUS: DONE 2026-09-07 — `leptris.html` gained `mode=` ("html4" default / "whatwg"); the default entry switched to `leptris_parse_html4_string` to keep the Nokogiri-class contract stable; lxml's leading-script lift divergence documented and reported on #659.**

# 16 — HTML two-mode surface (P1)

## Problem
1.9.104 changed `leptris_parse_html_string` semantics to WHATWG
(expanded head-lift set) — silently diverging the binding's
documented lxml-parity contract — and added
`leptris_parse_html4_string` as the compat entry.

## Plan
`document()/fromstring(html, mode="html4")`: the mode selects the
engine entry from a table (OCP: a third mode is a dict row);
default = html4 (compat); invalid mode raises ValueError. cdef +
REQUIRED_CORE. Specs: default keeps script in body (Nokogiri
shape; lxml lifts — known divergence, reported #659), whatwg lifts
to head, ValueError on bad mode.

## Acceptance
All prior HTML pins hold unchanged on the default; mode specs green.
