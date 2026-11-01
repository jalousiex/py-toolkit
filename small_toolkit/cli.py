"""命令行辅助：分组子命令帮助、CLI / 占位符 / 环境变量 / 默认值的参数回退。"""

from __future__ import annotations

import argparse
import ast
import os
import re
from collections.abc import Mapping, Sequence
from typing import Any

#: 平台代码参数占位符（形如 ``${name}``）：解析时视为未设置
_PLACEHOLDER = re.compile(r"^\$\{[^{}]+\}$")

CommandGroups = Mapping[str, Sequence[tuple[str, str]]]


def add_grouped_subparsers(
    parser: argparse.ArgumentParser,
    groups: CommandGroups,
    *,
    dest: str = "command",
    footer: str | None = None,
) -> dict[str, argparse.ArgumentParser]:
    """注册按领域分组的子命令，并将统一命令清单加入帮助描述。"""
    commands = [(name, help_text) for items in groups.values() for name, help_text in items]
    if not commands:
        raise ValueError("命令分组不能为空")

    width = max(len(name) for name, _ in commands)
    lines = []
    for title, items in groups.items():
        if lines:
            lines.append("")
        lines.append(f"{title}:")
        lines.extend(f"  {name:<{width}}  {help_text}" for name, help_text in items)
    if footer:
        lines.extend(("", footer))

    description = parser.description or ""
    parser.description = "\n\n".join(part for part in (description, "\n".join(lines)) if part)
    parser.formatter_class = argparse.RawDescriptionHelpFormatter

    subparsers = parser.add_subparsers(dest=dest, metavar="命令")
    result = {}
    for name, _ in commands:
        sub = subparsers.add_parser(name)
        # 缺必选参数时显示帮助而非 argparse 默认的 usage+error
        sub.error = lambda msg, self=sub: (self.print_help(), self.exit(2))
        result[name] = sub
    return result


def add_parameter(
    parser: argparse.ArgumentParser,
    option: str,
    *aliases: str,
    default: Any = None,
    parameter: Any = None,
    env: str | None = None,
    **kwargs: Any,
) -> None:
    """添加本地 CLI 参数，并登记平台代码参数占位符与环境变量回退。

    ``parameter`` 为平台注入的代码参数值，``env`` 为环境变量名；取值优先级由
    :func:`resolve_parameters` 统一处理（CLI → ``parameter`` → 环境变量 → ``default``）。
    """
    if not option.startswith("--"):
        raise ValueError("参数必须使用长选项，例如 --database")

    name = option[2:].replace("-", "_")
    # 属性名沿用既有工具链（UI 扫描器按此名读取参数规格），勿改名
    specs = getattr(parser, "_dataphin_parameter_specs", {})
    if name in specs:
        raise ValueError(f"重复的参数配置: {option}")

    parser.add_argument(option, *aliases, default=None, **kwargs)
    specs[name] = {"default": default, "parameter": parameter, "env": env, "type": kwargs.get("type")}
    parser._dataphin_parameter_specs = specs
    parser.set_defaults(_dataphin_parameter_specs=specs)


def resolve_parameters(args: argparse.Namespace) -> argparse.Namespace:
    """按 CLI、平台代码参数、环境变量、默认值的顺序填充参数。"""
    for name, spec in getattr(args, "_dataphin_parameter_specs", {}).items():
        value = getattr(args, name)
        if _is_unset(value):
            value = _parameter_value(spec["parameter"])
        if _is_unset(value) and spec["env"]:
            value = os.getenv(spec["env"])
        if _is_unset(value):
            value = spec["default"]
        elif spec["type"] and isinstance(value, str):
            value = spec["type"](value)
        setattr(args, name, value)
    return args


def _is_unset(value: Any) -> bool:
    return value is None or value == "" or (isinstance(value, str) and _PLACEHOLDER.fullmatch(value))


def _parameter_value(value: Any) -> Any:
    if not isinstance(value, str) or _is_unset(value):
        return value
    if len(value) >= 2 and value[0] in "'\"" and value[-1] == value[0]:
        try:
            return ast.literal_eval(value)
        except (SyntaxError, ValueError):
            pass
    return value


def resolve_env_var(env: str, base_name: str) -> str | None:
    """按优先级解析多环境变量：

    1. ``{base_name}_LIST`` — 分号分隔的 ``env=value`` 格式（最高优先级）
    2. ``{base_name}_{ENV}`` — 单环境变量
    3. ``{base_name}`` — 仅 ``env=prod`` 时回退到原生变量名

    任一来源有值（含空字符串）即返回，全缺失返回 ``None``。非 prod 环境不会读原生变量，
    避免旧单环境凭据被误当作测试/开发环境配置。

    例（值由外部注入，本库不读写凭据）::

        # _LIST = "tst=doris-tst:8030;prod=doris-prod:8030"
        resolve_env_var("tst", "DW_doris_RW_url")  # -> "doris-tst:8030"
    """
    # 1. LIST 格式
    list_raw = os.environ.get(f"{base_name}_LIST", "").strip()
    if list_raw:
        for part in list_raw.split(";"):
            part = part.strip()
            if "=" in part:
                k, v = part.split("=", 1)
                if k.strip() == env:
                    return v.strip()
    # 2. 单环境变量 {KEY}_{ENV}
    env_val = os.environ.get(f"{base_name}_{env.upper()}", "").strip()
    if env_val:
        return env_val
    # 3. 回退原生变量（仅 prod 环境）
    if env.lower() == "prod":
        fallback = os.environ.get(base_name, "").strip()
        return fallback or None
    return None
