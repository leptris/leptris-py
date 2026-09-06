**STATUS: OPEN (blocked upstream by definition) — triggers and automation listed above; watcher armed for #875.**

# 08 — Blocked upstream: fix adoptions and new-engine bindings (P3)

Tracked, automated, not completable from this repo today:

1. **#875 fix** (dispatch-index capacity; CRITICAL, advisory live in
   README). Trigger: next libleptris tag. Action: build, red-first
   120-template golden, ship pin-bump release, remove advisory.
   Tag watcher armed.
2. **#869 digest** — signed off (on-demand yes / parse-time no).
   Trigger: `leptris_node_digest` in a release. Action: cdef + small
   `Element.digest()` surface + determinism specs.
3. **#878 RELAX NG** — endorsed with the RelaxNG(schema).validate()
   shape. Trigger: parse/validate/free trio in a release. Action:
   `CompiledSource` subclass (~15 lines by item 03's design) + core
   grammar goldens.
4. **#682/#659** — engine-side perf/conformance; ledger numbers on
   the issues; nothing binding-actionable.

Version note: items 1-3 ship under the `{c-full-semver}.{patch}`
scheme automatically (pin moves → .0; binding-only → .1).
