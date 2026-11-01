"""日志初始化：控制台着色、按环境隔离的文件日志与 ``--debug`` 开关。

默认只输出到控制台；``setup_job(..., log_file=True)`` 额外落盘到
``<产物根>/output/logs/``。控制台着色只在真终端生效——管道、重定向、子进程捕获
都不是真终端，一律纯文本；落盘日志始终纯文本。
"""

from __future__ import annotations

import argparse
import logging
import os
import re
from datetime import datetime
from pathlib import Path

from .outputs import env_suffix, get_output_dir

#: ``--debug`` 的统一帮助文案（口径：输出调用摘要、不输出完整请求/响应正文）
DEBUG_HELP = "启用 DEBUG 诊断日志（输出调用摘要，不输出完整请求/响应正文）"

#: ANSI 控制序列：消息正文按级别 / 角色着色（时间戳与级别名前缀保持终端默认色）
_RESET = "\033[0m"

#: 日志级别 -> 消息正文颜色（INFO 留空 = 终端默认色，不加控制序列）
_LEVEL_COLORS = {
    "DEBUG": "\033[36m",
    "INFO": "",
    "WARNING": "\033[33m",
    "ERROR": "\033[31m",
    "CRITICAL": "\033[31m",
}

#: INFO 行首角色标记 -> 整行颜色（允许缩进，判定前先 lstrip）。
#: ``▸`` 任务行保持默认色，故不登记。
_ROLE_COLORS = {
    "━━": "\033[1m\033[36m",  # 阶段标题：粗体青
    "≠": "\033[33m",  # 差异：黄
    "⚠": "\033[1m\033[33m",  # 告警：粗体黄
    "✗": "\033[1m\033[31m",  # 失败：粗体红
    "·": "\033[2m",  # 次级信息：暗淡
}

#: 行首「两空格 + 块内标签」只给标签着青色
_FIELD_LABELS = ("输入", "查询", "映射", "分组", "产物", "任务名模板", "管道目标", "结果")
_FIELD_LINE_RE = re.compile(
    "(  )(" + "|".join(sorted(_FIELD_LABELS, key=len, reverse=True)) + r")(\s)"
)


def _role_color(message: str) -> str:
    """消息行首角色标记对应的整行颜色；无标记返回空串（保持终端默认色）。"""
    stripped = message.lstrip()
    for marker, color in _ROLE_COLORS.items():
        if stripped.startswith(marker):
            return color
    return ""


def _message_offset(text: str, message: str) -> int | None:
    """消息在整行渲染结果里的起始位置（默认格式 = 前缀 + 消息后缀）。"""
    if not message or not text.endswith(message):
        return None
    return len(text) - len(message)


def _color_enabled(stream) -> bool:
    """控制台是否着色：真终端，且未被 ``NO_COLOR`` / ``TERM=dumb`` 关闭。

    管道、重定向、子进程捕获、平台调度都不是真终端 → 一律纯文本。
    ``NO_COLOR`` 按 no-color.org 约定：设了非空值即关闭。
    """
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("TERM", "").lower() == "dumb":
        return False
    isatty = getattr(stream, "isatty", None)
    return bool(isatty and isatty())


class _ColorFormatter(logging.Formatter):
    """给控制台的**消息正文**着色的 Formatter（时间戳 / 级别名前缀保持终端默认色）。

    角色标记（``━━`` / ``≠`` / ``⚠`` / ``✗`` / ``·``）优先于级别色——``⚠`` / ``✗``
    用角色表里的粗体色，其余按级别（WARNING 黄 / ERROR 红 / DEBUG 青）；INFO 无角色
    标记时再看「两空格 + 块内标签」（如 ``输入`` / ``任务名模板``），只给标签着青色。

    落盘日志不挂本 Formatter（文件 handler 用默认 Formatter），文件里始终是纯文本。
    """

    def format(self, record: logging.LogRecord) -> str:
        message = record.getMessage()
        text = super().format(record)
        offset = _message_offset(text, message)
        if offset is None:
            return text
        color = _role_color(message) or _LEVEL_COLORS.get(record.levelname, "")
        if color:
            return f"{text[:offset]}{color}{text[offset:]}{_RESET}"
        match = _FIELD_LINE_RE.match(message)
        if match:
            return (
                f"{text[: offset + match.start(2)]}\033[36m{match.group(2)}\033[0m"
                f"{text[offset + match.end(2):]}"
            )
        return text


class _LazyDirFileHandler(logging.FileHandler):
    """延迟建目录的 FileHandler：首次 emit 才 ``mkdir``，import 期不产生空目录。"""

    def __init__(self, filename: str | Path, encoding: str = "utf-8") -> None:
        super().__init__(filename, encoding=encoding, delay=True)
        self._dir_ready = False

    def emit(self, record: logging.LogRecord) -> None:
        if not self._dir_ready:
            Path(self.baseFilename).parent.mkdir(parents=True, exist_ok=True)
            self._dir_ready = True
        super().emit(record)


def setup_job(
    script_path: str | Path,
    *,
    log_file: bool | str | Path = False,
    level: int = logging.INFO,
    format: str = "%(asctime)s - %(levelname)s - %(message)s",
    datefmt: str = "%m-%d %H:%M:%S",
) -> logging.Logger:
    """初始化脚本运行环境：配置 logging。

    - 默认配置 StreamHandler（控制台输出）。
    - 控制台是真终端时按级别 / 角色着色（只给消息正文上色）；管道、重定向、子进程
      捕获下自动关闭，落盘文件始终是纯文本。
    - ``log_file=True`` 时自动在 ``<产物根>/output/logs/`` 下创建 ``<脚本名>_<YYYYMMDD>.log``
      文件处理器（非 tst 环境由主流程解析参数后调 :func:`set_log_env` 改名）。
    - ``log_file`` 为自定义字符串或 Path 时，创建对应文件处理器（相对路径基于 ``output/logs/``）。
    - 目录在**首次落日志时**才创建（import 期调用不产生空目录）。
    - 返回对应模块的 Logger。
    """
    console = logging.StreamHandler()
    handlers: list[logging.Handler] = [console]
    if log_file:
        if isinstance(log_file, bool):
            filename = f"{Path(script_path).stem}_{datetime.now():%Y%m%d}.log"
            log_path = get_output_dir(script_path, "logs", create=False) / filename
        else:
            log_path = Path(log_file)
            if not log_path.is_absolute():
                log_path = get_output_dir(script_path, "logs", create=False) / log_path
        handlers.append(_LazyDirFileHandler(log_path))

    logging.basicConfig(level=level, format=format, datefmt=datefmt, handlers=handlers, force=True)

    # 颜色只给控制台：文件日志保持 basicConfig 挂的默认 Formatter（纯文本）
    if _color_enabled(console.stream):
        console.setFormatter(_ColorFormatter(format, datefmt))
    return logging.getLogger(Path(script_path).stem)


#: setup_job 自动日志文件名（``<脚本名>_<YYYYMMDD>.log``）的识别模式
_AUTO_LOG_NAME_RE = re.compile(r"(.+)_(\d{8})\.log$")


def set_log_env(env: str | None) -> Path | None:
    """把 ``setup_job(log_file=True)`` 自动创建的文件日志按环境改名：非 tst 重写为
    ``<脚本名>@<env 小写>_<YYYYMMDD>.log``（如 ``intake_tool@prod_20261031.log``）。

    在脚本 ``main()`` 解析出 ``-e/--env`` 后调用一次；tst（含未传，大小写不敏感）不动，
    保持 ``<脚本名>_<YYYYMMDD>.log``。只处理自动命名的 FileHandler；自定义
    ``log_file=...`` 的不动。env 归一与产物目录同一套（:func:`env_suffix`）。
    调用前已写出的行留在原名文件里（handler 是 ``delay=True``，通常调用时文件尚未创建）。
    返回新日志路径；无需改名或没有自动命名 FileHandler 时返回 ``None``。
    """
    suffix = env_suffix(env)
    if not suffix:
        return None
    root = logging.getLogger()
    new_path: Path | None = None
    for handler in root.handlers[:]:
        if not isinstance(handler, logging.FileHandler):
            continue
        old_path = Path(handler.baseFilename)
        match = _AUTO_LOG_NAME_RE.fullmatch(old_path.name)
        if not match:
            continue
        # 先剥离可能已有的 @env 后缀，保证连续调用幂等（不叠成 @prod@uat@prod）
        base = match.group(1).split("@", 1)[0]
        candidate = old_path.with_name(f"{base}{suffix}_{match.group(2)}.log")
        if candidate == old_path:
            continue
        replacement = _LazyDirFileHandler(candidate)
        replacement.setFormatter(handler.formatter)
        replacement.setLevel(handler.level)
        root.removeHandler(handler)
        handler.close()
        root.addHandler(replacement)
        new_path = candidate
    return new_path


def add_debug_argument(parser: argparse.ArgumentParser, *, help: str = DEBUG_HELP) -> None:
    """注册 ``--debug``：输出诊断日志与调用摘要（完整请求/响应正文仍不落日志）。

    默认 ``argparse.SUPPRESS``，因此带子命令的入口可在顶层与子命令各注册一次，
    使 ``--debug`` 放在子命令前或后都能生效；判断统一交给 :func:`enable_debug_logging`。
    """
    parser.add_argument("--debug", action="store_true", default=argparse.SUPPRESS, help=help)


def enable_debug_logging(args: argparse.Namespace, *, level: int = logging.DEBUG) -> None:
    """``--debug`` 生效：root 与既有 handler 一并切到 ``level``；未开启时不动任何级别。

    :func:`setup_job` 用 ``basicConfig(handlers=[...], force=True)`` 建好 handler，
    只改 root 级别不足以放行 DEBUG，故两层都改。
    """
    if not getattr(args, "debug", False):
        return
    root = logging.getLogger()
    root.setLevel(level)
    for handler in root.handlers:
        handler.setLevel(level)
