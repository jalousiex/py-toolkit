# small_toolkit

纯标准库的通用 Python 小工具集合：产物目录、日志初始化、命令行参数、终端表格。

## 边界

- **零第三方依赖**：只用标准库（`pathlib` / `logging` / `argparse` / `unicodedata`）。
- **无凭据、无内网地址**：不读环境里的密钥，不内置任何内网域名；环境变量只做**名字**层面的回退。
- 只抽跨项目复用的通用能力，业务逻辑（平台 SDK、数据源客户端、领域规则）留在各自仓库。

## 安装

从 tag 安装（跨仓依赖固定到 tag，不跟浮动分支）：

```bash
uv add "small_toolkit @ git+https://github.com/jalousiex/py-toolkit.git@v0.1.1"
```

本地开发：

```bash
uv sync
uv run pytest -q
```

## 分区

| 模块 | 内容 |
| --- | --- |
| `small_toolkit.outputs` | `output_root` / `output_dir` / `get_output_dir` / `tool_output_dir` / `display_path` / `env_suffix` / `tool_dir_name` / `save_json` / `write_json` / `save_bytes` / `save_response` |
| `small_toolkit.logs` | `setup_job`（控制台着色 + 延迟建目录的文件日志）/ `set_log_env` / `add_debug_argument` / `enable_debug_logging` |
| `small_toolkit.cli` | `add_grouped_subparsers` / `add_parameter` / `resolve_parameters` / `resolve_env_var` |
| `small_toolkit.table` | `print_table` / `print_grouped_table` / `print_tree` |

顶层 `small_toolkit` 已重导出全部公开 API，`from small_toolkit import setup_job, tool_output_dir` 即可。

## 产物目录约定

```text
<产物根>/output/<分类 slug>/<工具名>[@<env 小写>]/<产物类型>/
```

- 产物根：默认运行目录；从运行目录向上命中便携标记（`WORKSPACE_MARKERS`，默认
  `.workspace-root` / `.dataphin.jsonc`）时归到该目录，工作区任意子目录启动都落到工作区根。
- 环境后缀：`tst`（含未传，大小写不敏感）无后缀；其它环境 `@<env 小写>`，同一套归一
  同时作用于产物目录与日志文件名。
- 落盘统一走 `save_json` / `write_json` / `save_bytes`：自动建父目录；`save_json` 不补末尾
  换行、非序列化对象按 `str()` 落盘，`write_json` 末尾补换行。

```python
from small_toolkit import setup_job, tool_output_dir

setup_job(__file__, log_file=True)
out = tool_output_dir("data_dev", "intake_tool", env="prod", create=True)
```

## 日志与 `--debug`

`setup_job()` 只在**真终端**给消息正文着色；管道、重定向、子进程捕获、`NO_COLOR`
下一律纯文本，落盘日志始终纯文本。`add_debug_argument()` 默认 `argparse.SUPPRESS`，
顶层与子命令各注册一次也不会互相覆盖，判断统一交给 `enable_debug_logging()`。

## 命令行回退顺序

`add_parameter()` 登记后，`resolve_parameters()` 按
**CLI → 平台代码参数（`parameter`）→ 环境变量（`env`）→ 默认值** 填充；
平台占位符（`${name}`）按未设置处理。`resolve_env_var(env, base)` 依次读
`{base}_LIST`（`env=value;...`）、`{base}_{ENV}`，仅 `prod` 时回退原生 `{base}`。

## 版本

`pyproject.toml` 的 `version` 为唯一来源；发版打 tag（`v0.1.1`），引用方按 tag 固定。

## 发布

PyPI 走 GitHub Actions + Trusted Publishing（OIDC，不用 API token）：

- 先手动跑 `publish-test`（`workflow_dispatch`）发 TestPyPI 验证，不占正式版本号；
- 正式发布：`pyproject.toml` 升版本 → 打 tag `v*` → push tag，`publish` 工作流构建并上传。
- 工作流会先校验 tag 与 `pyproject.toml` 的 `version` 一致，不一致直接失败（PyPI 同版本不可覆盖）。
- GitHub 仓库需要预先配置 PyPI 的 pending publisher（Owner / Repository / Workflow / Environment 四项与工作流一致）。

