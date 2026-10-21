# rule-preserve

[简体中文](README.md) · [MIT license](LICENSE) · [Provenance](PROVENANCE.md)

Check whether important source rules and exceptions survive a split into core and task-specific files.

Version 0.2.0 provides only block-preservation checks in one runtime module, `rule_preserve.py`. It requires Python 3.9+ and has no third-party runtime dependencies. Checks run locally without model calls or network access and do not modify inputs.

## Try it

From the project directory, without installation:

```sh
python3 -m rule_preserve check examples/source.md examples/preserved examples/spec.json
```

Expect JSON with `pass: true` and exit `0`. The following cases deliberately fail with exit `1`:

```sh
python3 -m rule_preserve check examples/source.md examples/missing-exception examples/spec.json
python3 -m rule_preserve check examples/source.md examples/duplicated examples/spec.json
```

The first omits an exception; the second duplicates it. All example data is synthetic. Inspect the [source](examples/source.md) and [reviewed inventory](examples/spec.json).

Optionally install the local source and use the console entry point:

```sh
python3 -m pip install .
rule-preserve check examples/source.md examples/preserved examples/spec.json
```

Building requires setuptools and wheel; running the checker does not. A prebuilt local wheel can be installed offline with `pip install --no-index --no-deps <local-wheel-path>`. This project has not been published to PyPI. Do not substitute a similarly named remote package.

## Check your own rules

Review the source manually. Select important obligations together with their conditions, order, scope, and exceptions. An inventory looks like this:

```json
{
  "source_sha256": "<64 lowercase SHA-256 hex characters of raw source bytes>",
  "core_files": ["core.md"],
  "blocks": [{"id": "edit-policy", "start": 10, "end": 12}]
}
```

- Line ranges are 1-based and inclusive; block IDs must be unique.
- The source hash locks the reviewed source version. Review ranges and content again before updating the hash after any source change.
- Core paths are relative to the candidate directory. Use an isolated candidate copy containing only regular UTF-8 `.md` and `.txt` files, without symlinks or other files. Keep the JSON inventory outside that directory.
- Each declared block must occur exactly once across the whole candidate tree, in a declared core file.
- Comparison preserves bytes and line endings: LF, CRLF, indentation, and prefixes matter.

Compute a hash and run the check:

```sh
python3 -c "import hashlib, pathlib; print(hashlib.sha256(pathlib.Path('examples/source.md').read_bytes()).hexdigest())"
python3 -m rule_preserve check SOURCE CANDIDATE SPEC
```

Python callers may use `from rule_preserve import check` with a source `Path`, candidate-directory `Path`, and inventory dictionary.

## Results

`check` writes UTF-8 JSON to stdout. Results include `schema_version`, `command`, and `pass`; valid checks also include per-block `occurrences`, `in_declared_core`, and hashes. Invalid inputs have an `error` field.

| Exit | Meaning |
| --- | --- |
| `0` | Every declared block passes |
| `1` | Valid input, but a block is missing, duplicated, or outside the core |
| `2` | Invalid arguments, paths, source hash, UTF-8, or inventory |

Help and version use ordinary text. The earlier `audit` feature is not included in this distribution.

## Limits

This tool verifies only human-declared source blocks. It does not prove that the inventory is complete, rules are semantically equivalent, or an agent loads or follows them. It does not compress, rewrite, delete, or move rules, and does not measure token or subscription-quota savings.

## Tests and license

```sh
python3 -B -m unittest discover -s tests -v
```

Licensed under [MIT](LICENSE). Implementation, tests, and documentation include AI-assisted work. [Provenance](PROVENANCE.md) records the reconstructable checker patch chain and the scope of this single-feature distribution.
