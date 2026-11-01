"""产物目录与落盘：路径拼装、环境后缀、JSON 与原始字节写入。

产物根默认是运行目录；从运行目录向上命中便携工作区标记（:data:`WORKSPACE_MARKERS`）
时归到该目录，便于在工作区任意子目录启动脚本。所有落盘路径都经 :func:`output_dir`
拼装，不在各脚本里手写 ``Path("output")``。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

#: 便携工作区标记：从运行目录向上命中任一个即把产物根切到该目录所在层级。
#: ``.workspace-root`` 为通用标记；``.dataphin.jsonc`` 保留以兼容既有工作区。
WORKSPACE_MARKERS = (".workspace-root", ".dataphin.jsonc")


def output_root(start: str | Path | None = None) -> Path:
    """产物根：默认运行目录（cwd）；cwd 起向上命中便携标记时用它所在目录。

    便携工作区（根目录放 ``.workspace-root`` / ``.dataphin.jsonc``）里无论从哪一层
    子目录启动，产物都归到工作区根；普通目录仍是 cwd 本身（产物归到运行位置）。
    """
    base = Path(start) if start is not None else Path.cwd()
    base = base.resolve()
    for candidate in (base, *base.parents):
        if any((candidate / marker).is_file() for marker in WORKSPACE_MARKERS):
            return candidate
    return base


def output_dir(*segments: str | Path, create: bool = False) -> Path:
    """产物根下的 ``output/<segments...>``；``create=True`` 时确保目录存在。

    所有落盘路径的唯一拼装入点：分类、工具名、产物类型都作为片段传入。
    """
    directory = output_root() / "output"
    for segment in segments:
        if segment:
            directory = directory / segment
    if create:
        directory.mkdir(parents=True, exist_ok=True)
    return directory


def get_output_dir(
    script_path: str | Path | None, *subdirs: str | Path, create: bool = True
) -> Path:
    """获取工具产物目录：``<产物根>/output/<subdirs...>``，默认确保目录存在。

    ``script_path`` 仅作调用方自述（日志定位用），不参与路径计算；产物根见
    :func:`output_root`，与脚本所在路径无关。

    - get_output_dir(__file__) -> <root>/output
    - get_output_dir(__file__, "intake_tool", tag) -> <root>/output/intake_tool/<tag>
    - get_output_dir(__file__, create=False) -> 只算路径、不建目录（import 期用）

    带分类层与环境后缀的调用优先用 :func:`tool_output_dir`；本函数保留给仓库级
    构建/辅助产物（``output/_build/...``）。
    """
    return output_dir(*subdirs, create=create)


def tool_output_dir(
    group: str, tool_name: str, *subdirs: str | Path, env: str | None = None, create: bool = False
) -> Path:
    """业务工具产物目录：``<产物根>/output/<group>/<tool>[@env]/<subdirs...>``。

    ``group`` 是业务分类英文 slug，与调用方仓库的分类目录一一对应；
    ``env`` 按 :func:`tool_dir_name` 规则加后缀。
    """
    return get_output_dir(None, group, tool_dir_name(tool_name, env), *subdirs, create=create)


def display_path(path: str | Path) -> str:
    """日志里的文件路径展示：优先相对产物根，其次相对运行目录，都不在则用绝对路径。

    不产生 ``..``；输出保留本机分隔符（Windows 为 ``\\``）。所有落盘日志共用这一份规则。
    """
    absolute = Path(path).resolve()
    for base in (output_root(), Path.cwd().resolve()):
        try:
            return str(absolute.relative_to(base))
        except ValueError:
            continue
    return str(absolute)


def env_suffix(env: str | None = None) -> str:
    """环境归一后缀：tst（含未传，大小写不敏感）为空串，其余环境 ``@<env 小写>``。

    产物目录（:func:`tool_dir_name`）与日志文件名（:func:`set_log_env`）共用这一套归一，
    避免出现两种写法；归一**只作用于本地目录/文件命名**，不改动传给外部系统的 env 原值。
    """
    return "" if not env or env.lower() == "tst" else f"@{env.lower()}"


def tool_dir_name(tool_name: str, env: str | None = None) -> str:
    """产物工具目录名：默认环境 tst（含未传，大小写不敏感）不带后缀，其余环境
    ``{tool_name}@<env 小写>``。

    默认环境存量路径零变化，其它环境在工具目录名后加 ``@<env 小写>`` 后缀，如
    ``task_tool@prod``、``-e UAT`` → ``task_tool@uat``；显式传给 ``--output-dir``
    等的完整目录不套用本规则。
    """
    return tool_name + env_suffix(env)


def _dump_json(
    path: str | Path,
    data,
    *,
    indent: int,
    newline: bool,
    stringify: bool,
) -> Path:
    """JSON 落盘内核：自动建父目录，UTF-8 写出，可选末尾换行 / 非序列化对象转字符串。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(
        data, ensure_ascii=False, indent=indent, default=str if stringify else None
    )
    if newline:
        text += "\n"
    path.write_text(text, encoding="utf-8")
    return path


def save_json(path: str | Path, data, *, indent: int = 2) -> Path:
    """把数据按 UTF-8 JSON 写到 ``path``（自动建父目录），返回落盘路径。

    非序列化对象按 ``str()`` 落盘（如 datetime）；不追加末尾换行。
    """
    return _dump_json(path, data, indent=indent, newline=False, stringify=True)


def write_json(path: str | Path, data, *, indent: int = 2) -> Path:
    """把对象写成 UTF-8 JSON 文件（``ensure_ascii=False``、末尾换行），返回写入路径。

    目录不存在时自动创建。与 :func:`save_json` 的区别仅在末尾换行与是否容错非序列化对象。
    """
    return _dump_json(path, data, indent=indent, newline=True, stringify=False)


def save_bytes(path: str | Path, content: bytes) -> Path:
    """把原始字节写到 ``path``（自动建父目录），返回落盘路径。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def save_response(
    script_path: str,
    category: str,
    name: str,
    data,
    *,
    output_dir: str | Path | None = None,
    tool_name: str | None = None,
    env: str | None = None,
    group: str | None = None,
    timestamp_fmt: str = "%Y%m%d",
) -> Path | None:
    """保存原始响应，默认路径为 ``<产物根>/output/[<分类>/]<tool名称[@{env}]/<子类别>``。

    ``group`` 为业务分类 slug（见 :func:`tool_output_dir`）；不传时保持扁平路径
    ``output/<tool>/<子类别>``（仅兼容仓库级/未分类调用）。``data`` 为空时不落盘。
    """
    if not data:
        return None
    script = Path(script_path).resolve()
    if output_dir is not None:
        directory = Path(output_dir)
        directory.mkdir(parents=True, exist_ok=True)
    elif group:
        directory = tool_output_dir(group, tool_name or script.stem, category, env=env, create=True)
    else:
        directory = get_output_dir(script, tool_dir_name(tool_name or script.stem, env), category)
    path = directory / f"{name}_{datetime.now().strftime(timestamp_fmt)}.json"
    save_json(path, data)
    logging.getLogger(__name__).info("  响应：%s", display_path(path))
    return path
