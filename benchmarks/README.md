# Benchmarks

`python -m benchmarks.matrix` compares **leptris** against `lxml.etree`,
`xml.etree.ElementTree` and `xml.dom.minidom` on the same fixtures and
iteration counts as the Ruby matrix
(`leptris-ruby/benchmark/leptris_vs_nokogiri.rb`), so the two matrices
are comparable.

## Running

```bash
pip install .[bench]          # pins lxml
export LEPTRIS_LIB_PATH=/path/to/libleptris.dylib
python -m benchmarks.matrix
```

Output: an environment header (python, platform, library versions,
pinned libleptris version), per-operation timings in µs/iteration, a
Markdown summary table with a winner column, and a JSON dump after the
`--- results json ---` marker (`{"python", "platform", "libs",
"results": [{"lib", "op", "us" | "skipped"}]}`).

## Methodology

- Warmup of n/10 iterations before each timed loop (kills cold-start
  artifacts: dlopen, code-signature checks); `gc.collect()` before
  each loop; `time.perf_counter()`.
- Iterations: parse small 5000, parse medium 1000, queries 10000,
  traversal 2000, serialize 1000.
- Missing libraries → skipped rows; unsupported operations → skipped
  with a reason (ElementTree has no `count()`/union; minidom has no
  XPath). The matrix degrades gracefully and always exits 0.
- **Losses are results.** Nothing is deleted or muted.

## Where the canonical results live

The `python-benchmark` workflow in the C repository
(`leptris/leptris`) runs this matrix nightly on ubuntu-latest and
macos-14 and uploads `python-benchmark-results-<os>` artifacts
(90-day retention). Hand-measured numbers do not go on the website;
the site consumes those artifacts.

Version-label every published number: the leptris version
(`leptris.__version__`), the libleptris pin
(`libleptris-version.txt`), and lxml per the `[bench]` extra at
measurement time.
