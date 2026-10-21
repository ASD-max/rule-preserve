# Provenance / 来源

## Included scope

This distribution contains one runtime Python module implementing declared-block preservation checks, newly prepared specification-based tests, synthetic examples, and project documentation. It does not contain the structural-audit implementation or the earlier audit tests.

The checker core descends from the locally maintained `zh-rule-context-optimizer/scripts/check_core_blocks.py`. Its historical Add File and Update patches were parsed as data and replayed in memory. A coherent patch branch reconstructs the complete current input byte for byte:

| Stage | Lines | SHA-256 |
| --- | --- | --- |
| Add File | 88 | `fa303d48cc12889afbf100bacf3b31b3bfe3b420e9fa9aa45e159967d879ac65` |
| Update | 109 | `da7763e09a9ac180b247ded6ba28ca0584973609248756ebc85b7cbf9d0a4f3b` |
| Final Update and original local checker | 115 | `7b97884d68efa4bd95076de96bc8291bed300351d1315989179703c41d74857a` |

The historical records include a local request to create a Chinese rule-management skill and locally proposed code patches. No upstream copyright notice, external source attribution, or conflicting license was found in the included input. Some retained historical containers have inconsistent timestamps; their container times are not claimed as exact authorship times. Raw conversations and machine-specific paths are not distributed here.

## Changes for this distribution

- The checker and command-line wrapper are combined into `rule_preserve.py`.
- Source-file, UTF-8, inventory-shape, SHA-256, and block-ID validation produce explicit errors.
- The console entry point and `python -m` command accept only the `check` subcommand.
- Errors use JSON and exit 2; valid preservation failures exit 1.
- Tests are newly written from a functional specification for this distribution. Earlier test files were not copied.
- Synthetic examples were created during the local project-preparation work, with no business or account data.

## License decision

At the project owner's request, this scoped distribution is prepared under the [MIT license](LICENSE), attributed to John (ASD-max). This decision uses the recoverable local checker history and the new packaging, tests, and documentation. It does not relicense the excluded audit implementation or change the status of the earlier dual-feature candidate.

[OpenAI's Terms of Use](https://openai.com/policies/terms-of-use/) describe output rights between the user and OpenAI, subject to applicable law, and preserve third-party rights. The [OSI MIT text](https://opensource.org/license/mit) is the license template used here. This provenance record is a technical source assessment, not a determination of every possible third-party claim or copyright protection for AI-generated portions.

## Release status

Version 0.2.0 is prepared locally for review. No GitHub repository, package-registry release, or open-source program application has been published by this preparation step. Repository-name and registry-name availability are not asserted.
