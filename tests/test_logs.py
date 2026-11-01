"""日志契约：控制台着色、非真终端关闭着色、``--debug`` 生效。

守三条：① 真终端时**消息正文**带级别 / 角色色（前缀保持默认色）；② 非真终端
（管道 / 重定向 / 子进程捕获）无控制序列；③ 落盘日志与 ``NO_COLOR`` 下一律纯文本。
"""

import argparse
import io
import logging
import sys

import pytest

from toolkit.logs import _ColorFormatter, add_debug_argument, enable_debug_logging, setup_job


class _TtyStream(io.StringIO):
    """带 isatty() 的假流（StringIO 默认返回 False）。"""

    def isatty(self) -> bool:
        return True


@pytest.fixture(autouse=True)
def pin_color_env(monkeypatch):
    """隔离环境着色开关：终端宿主可能注入 NO_COLOR / TERM=dumb，会把用例结论带偏。"""
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("TERM", raising=False)


@pytest.fixture
def restore_root_handlers():
    """还原 root 的 handler 与级别（setup_job 的 basicConfig(force=True) 会清掉 pytest 挂的 handler）。"""
    root = logging.getLogger()
    handlers = list(root.handlers)
    level = root.level
    yield
    root.handlers = []
    for handler in handlers:
        root.addHandler(handler)
    root.setLevel(level)


def test_color_formatter_colors_only_message_body():
    """WARNING：只有消息正文黄色，时间戳 / 级别名前缀保持终端默认色。"""
    formatter = _ColorFormatter("%(levelname)s - %(message)s")
    record = logging.LogRecord("job", logging.WARNING, __file__, 1, "boom", None, None)

    text = formatter.format(record)

    assert text == "WARNING - \033[33mboom\033[0m"


def test_color_formatter_leaves_info_uncolored():
    """INFO 不加控制序列（终端默认色）。"""
    formatter = _ColorFormatter("%(levelname)s - %(message)s")
    record = logging.LogRecord("job", logging.INFO, __file__, 1, "hi", None, None)

    text = formatter.format(record)

    assert "\033[" not in text


def test_setup_job_colors_console_on_tty(monkeypatch, restore_root_handlers):
    """真终端：控制台输出带颜色。"""
    stream = _TtyStream()
    monkeypatch.setattr(sys, "stderr", stream)

    log = setup_job(__file__)
    log.warning("boom")

    assert "\033[33m" in stream.getvalue()


def test_setup_job_no_color_when_not_tty(monkeypatch, restore_root_handlers):
    """非真终端：无控制序列。"""
    stream = io.StringIO()
    monkeypatch.setattr(sys, "stderr", stream)

    log = setup_job(__file__)
    log.warning("boom")

    assert "\033[" not in stream.getvalue()


def test_setup_job_no_color_with_no_color_env(monkeypatch, restore_root_handlers):
    """NO_COLOR 非空：即使是真终端也不着色。"""
    monkeypatch.setenv("NO_COLOR", "1")
    stream = _TtyStream()
    monkeypatch.setattr(sys, "stderr", stream)

    log = setup_job(__file__)
    log.warning("boom")

    assert "\033[" not in stream.getvalue()


def test_log_file_stays_plain_text(tmp_path, monkeypatch, restore_root_handlers):
    """落盘日志不带控制序列。"""
    monkeypatch.chdir(tmp_path)
    script = tmp_path / "job.py"
    script.touch()
    stream = _TtyStream()
    monkeypatch.setattr(sys, "stderr", stream)

    log = setup_job(script, log_file=True)
    log.warning("boom")

    logs = list((tmp_path / "output" / "logs").glob("job_*.log"))
    assert len(logs) == 1
    assert "\033[" not in logs[0].read_text(encoding="utf-8")


def _info_record(message: str) -> logging.LogRecord:
    return logging.LogRecord("job", logging.INFO, __file__, 1, message, None, None)


def test_info_phase_title_is_bold_cyan():
    """阶段标题 ``━━``：正文粗体青，前缀默认色。"""
    text = _ColorFormatter("%(levelname)s - %(message)s").format(
        _info_record("━━ 阶段 1/3 · 匹配源表与预检目标 ━━━")
    )

    assert text.startswith("INFO - \033[1m\033[36m━━")
    assert text.endswith("━━━\033[0m")


def test_info_diff_marker_is_yellow_with_indent():
    """差异行 ``≠``（可带缩进）：正文黄。"""
    text = _ColorFormatter("%(levelname)s - %(message)s").format(
        _info_record("    ≠ Params.RUNTYPE: 平台=I → 本地=F")
    )

    assert text.startswith("INFO - \033[33m    ≠")
    assert text.endswith("\033[0m")


def test_info_warning_marker_is_bold_yellow():
    """告警行 ``⚠``：正文粗体黄。"""
    text = _ColorFormatter("%(levelname)s - %(message)s").format(
        _info_record("    ⚠ 内存上调至 1024MB")
    )

    assert text.startswith("INFO - \033[1m\033[33m    ⚠")


def test_info_field_label_colors_only_label():
    """块内标签只给标签着青色，正文保持默认色。"""
    text = _ColorFormatter("%(levelname)s - %(message)s").format(
        _info_record("  输入  table-list 2 行")
    )

    assert "\033[36m输入\033[0m  table-list 2 行" in text
    assert not text.startswith("\033[36m")


def test_info_task_line_stays_plain():
    """任务行 ``▸`` 保持默认色（不整行着色）。"""
    text = _ColorFormatter("%(levelname)s - %(message)s").format(
        _info_record("  ▸ edc_server1.tbl → ODS_CLD.T  (2 字段) · 无差异 · 新建")
    )

    assert "\033[" not in text


def test_warning_marker_uses_bold_role_color():
    """WARNING 行首 ``⚠``：角色色（粗体黄）优先于级别色，前缀保持默认色。"""
    record = logging.LogRecord("job", logging.WARNING, __file__, 1, "    ⚠ 内存上调至 1024MB", None, None)
    text = _ColorFormatter("%(levelname)s - %(message)s").format(record)

    assert text == "WARNING - \033[1m\033[33m    ⚠ 内存上调至 1024MB\033[0m"


@pytest.fixture
def restore_root_levels():
    """还原 root 与既有 handler 的级别（enable_debug_logging 会直接改它们）。"""
    root = logging.getLogger()
    level = root.level
    handler_levels = [handler.level for handler in root.handlers]
    yield
    root.setLevel(level)
    for handler, handler_level in zip(root.handlers, handler_levels):
        handler.setLevel(handler_level)


def test_debug_flag_raises_root_and_existing_handlers(restore_root_levels):
    """传 --debug：root 与既有 handler 都切到 DEBUG。"""
    root = logging.getLogger()
    root.setLevel(logging.WARNING)
    handler = logging.StreamHandler()
    handler.setLevel(logging.WARNING)
    root.addHandler(handler)
    try:
        enable_debug_logging(argparse.Namespace(debug=True))

        assert root.level == logging.DEBUG
        assert handler.level == logging.DEBUG
    finally:
        root.removeHandler(handler)


def test_without_debug_flag_no_level_changes(restore_root_levels):
    """未传 --debug（连属性都没有）时不动任何级别。"""
    root = logging.getLogger()
    root.setLevel(logging.WARNING)
    handler = logging.StreamHandler()
    handler.setLevel(logging.ERROR)
    root.addHandler(handler)
    try:
        enable_debug_logging(argparse.Namespace())

        assert root.level == logging.WARNING
        assert handler.level == logging.ERROR
    finally:
        root.removeHandler(handler)


def test_add_debug_argument_defaults_to_suppress():
    """``--debug`` 默认 SUPPRESS：顶层与子命令各注册一次时，未传不会互相覆盖。"""
    parser = argparse.ArgumentParser()
    add_debug_argument(parser)

    args = parser.parse_args([])

    assert not hasattr(args, "debug")
