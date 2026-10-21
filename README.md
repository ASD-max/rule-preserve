# rule-preserve

[English](README.en.md) · [MIT 许可](LICENSE) · [来源](PROVENANCE.md)

把一份规则文件拆成核心与按需模块后，检查你选定的重要条款和例外是否仍完整保留。

0.2.0 只提供规则块保留检查，运行代码是一个 `rule_preserve.py` 文件。需要 Python 3.9 或以上，无运行时第三方依赖。工具在本地只读运行，不调用模型或网络服务。

## 立即试用

进入项目目录，无需安装：

```sh
python3 -m rule_preserve check examples/source.md examples/preserved examples/spec.json
```

应得到 JSON，顶层 `pass` 为 `true`，退出码为 `0`。再试两种失败情形：

```sh
python3 -m rule_preserve check examples/source.md examples/missing-exception examples/spec.json
python3 -m rule_preserve check examples/source.md examples/duplicated examples/spec.json
```

它们都应退出 `1`：前者遗漏维护例外，后者把同一例外保留了两份。所有例子均为虚构；[源文件](examples/source.md)与[人工清单](examples/spec.json)可以直接检查。

也可安装本地源码，再使用相同的命令：

```sh
python3 -m pip install .
rule-preserve check examples/source.md examples/preserved examples/spec.json
```

构建安装需要 setuptools 和 wheel，工具运行本身无需这些依赖。使用已构建 wheel 时，可通过 `pip install --no-index --no-deps <本地wheel路径>` 离线安装。这个项目尚未发布到 PyPI，不要把安装命令改为从同名远程包安装。

## 检查自己的文件

先人工确认要保护的条款，包括它的条件、顺序、适用范围和例外。清单示意：

```json
{
  "source_sha256": "<源文件原始字节的64位小写SHA-256>",
  "core_files": ["core.md"],
  "blocks": [{"id": "edit-policy", "start": 10, "end": 12}]
}
```

- `start`、`end` 是从 1 开始、包含两端的完整行范围；每个块的 `id` 必须唯一。
- `source_sha256` 绑定人工审核过的源版本。源文件变化后，重新核对条款和行号，再更新清单。
- `core_files` 是相对候选目录的路径。候选目录应是单独的规则文本副本，只含普通 UTF-8 `.md`／`.txt` 文件，不含符号链接或其他文件。把 JSON 清单放在候选目录外。
- 每个声明块在整棵候选目录中必须恰好出现一次，且出现位置必须属于声明的核心文件。
- 比较保留原始字节和换行符；LF、CRLF、缩进或前缀不同都会影响匹配。

计算哈希并运行：

```sh
python3 -c "import hashlib, pathlib; print(hashlib.sha256(pathlib.Path('examples/source.md').read_bytes()).hexdigest())"
python3 -m rule_preserve check SOURCE CANDIDATE SPEC
```

也可以在 Python 中调用 `from rule_preserve import check`；三个参数分别为源文件的 `Path`、候选目录的 `Path` 和清单字典。

## 结果与退出码

`check` 把 UTF-8 JSON 写入标准输出。结果包含 `schema_version`、`command`、`pass`，有效检查还包含每块的 `occurrences`、`in_declared_core` 和哈希；无效输入使用 `error` 字段。

| 退出码 | 含义 |
| --- | --- |
| `0` | 所有声明块均通过 |
| `1` | 输入有效，但有声明块缺失、重复或不在核心文件中 |
| `2` | 参数、路径、源哈希、UTF-8 或清单无效 |

`--help` 和 `--version` 输出普通文本。旧版的 `audit` 命令不在这个发行版中。

## 能力边界

工具只验证你声明的原文块，不判断清单是否完整、规则是否语义等价，也不证明 Agent 一定加载或遵守这些规则。它不自动压缩、改写、删除或移动规则，不计量 token 或订阅额度节省。规则正文由你选择，清单审核仍由你负责。

## 测试与许可

```sh
python3 -B -m unittest discover -s tests -v
```

本项目使用 [MIT 许可](LICENSE)，含 AI 辅助编写的实现、测试和文档。[来源记录](PROVENANCE.md)说明检查器的可复算补丁链及此次封装范围。此许可用于本目录的单功能发行版。
