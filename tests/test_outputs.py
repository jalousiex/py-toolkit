"""产物目录、展示路径、JSON / 字节落盘与环境后缀。"""

import json
import logging
from datetime import datetime
from pathlib import Path

from small_toolkit import (
    display_path,
    get_output_dir,
    output_root,
    save_bytes,
    save_json,
    save_response,
    set_log_env,
    setup_job,
    tool_dir_name,
    tool_output_dir,
    write_json,
)


def test_tool_dir_name():
    """tst（含未传，大小写不敏感）不带后缀，其余环境加 @{env}。"""
    assert tool_dir_name("task_tool") == "task_tool"
    assert tool_dir_name("task_tool", "tst") == "task_tool"
    assert tool_dir_name("task_tool", "prod") == "task_tool@prod"


def test_tool_dir_name_env_case_insensitive():
    """TST / Tst 按默认环境归一，不产生带后缀目录。"""
    assert tool_dir_name("task_tool", "TST") == "task_tool"
    assert tool_dir_name("task_tool", "Tst") == "task_tool"


def test_tool_dir_name_suffix_lowercased():
    """非 tst 环境后缀统一小写：-e UAT → @uat。"""
    assert tool_dir_name("intake_tool", "UAT") == "intake_tool@uat"
    assert tool_dir_name("intake_tool", "Prod") == "intake_tool@prod"


def test_output_root_defaults_to_cwd(tmp_path, monkeypatch):
    """无便携标记：产物根就是运行目录。"""
    monkeypatch.chdir(tmp_path)
    assert output_root() == tmp_path.resolve()


def test_output_root_prefers_workspace_marker(tmp_path, monkeypatch):
    """cwd 上层有便携标记：产物根归到工作区根。"""
    (tmp_path / ".workspace-root").write_text("", encoding="utf-8")
    sub = tmp_path / "jobs" / "data_dev"
    sub.mkdir(parents=True)
    monkeypatch.chdir(sub)

    assert output_root() == tmp_path.resolve()


def test_output_root_keeps_dataphin_marker(tmp_path, monkeypatch):
    """既有 ``.dataphin.jsonc`` 工作区标记仍被识别。"""
    (tmp_path / ".dataphin.jsonc").write_text("{}", encoding="utf-8")
    sub = tmp_path / "jobs" / "data_dev"
    sub.mkdir(parents=True)
    monkeypatch.chdir(sub)

    assert output_root() == tmp_path.resolve()


def test_get_output_dir(tmp_path, monkeypatch):
    """产物目录 = <产物根>/output/<子目录>，与脚本所在目录无关。"""
    monkeypatch.chdir(tmp_path)
    script = tmp_path / "jobs" / "data_dev" / "my_script.py"
    script.parent.mkdir(parents=True)
    script.touch()

    out = get_output_dir(script)
    assert out == tmp_path / "output"
    assert out.is_dir()

    sub = get_output_dir(script, "2table_ddl", "EDC_039")
    assert sub == tmp_path / "output" / "2table_ddl" / "EDC_039"
    assert sub.is_dir()

    lazy = get_output_dir(script, "lazy_dir", create=False)
    assert lazy == tmp_path / "output" / "lazy_dir"
    assert not lazy.exists()


def test_tool_output_dir_adds_group_and_env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    out = tool_output_dir("data_dev", "intake_tool", "2table_ddl", env="prod", create=True)

    assert out == tmp_path / "output" / "data_dev" / "intake_tool@prod" / "2table_ddl"
    assert out.is_dir()


def test_display_path_prefers_output_root(tmp_path, monkeypatch):
    """展示路径相对产物根，保留本机分隔符。"""
    monkeypatch.chdir(tmp_path)
    out = tool_output_dir("platform", "platform_tool", "x", create=True)
    path = out / "a.json"
    path.write_text("{}", encoding="utf-8")

    assert display_path(path) == str(Path("output") / "platform" / "platform_tool" / "x" / "a.json")


def test_display_path_falls_back_to_absolute(tmp_path, monkeypatch):
    """不在产物根下时回退绝对路径，不产生 ``..``。"""
    monkeypatch.chdir(tmp_path)
    outside = tmp_path.parent / "elsewhere" / "a.json"

    assert display_path(outside) == str(outside.resolve())


def test_save_json_no_trailing_newline(tmp_path):
    """save_json：UTF-8、非序列化对象转字符串、不追加末尾换行。"""
    path = save_json(tmp_path / "a" / "b.json", {"名称": "值", "at": datetime(2026, 1, 1)})

    text = path.read_text(encoding="utf-8")
    assert not text.endswith("\n")
    assert json.loads(text)["名称"] == "值"


def test_write_json_has_trailing_newline(tmp_path):
    """write_json：目录自动创建、UTF-8、末尾补换行。"""
    path = write_json(tmp_path / "a" / "b.json", {"名称": "值"}, indent=4)

    text = path.read_text(encoding="utf-8")
    assert text.endswith("\n")
    assert '"名称": "值"' in text


def test_save_bytes(tmp_path):
    path = save_bytes(tmp_path / "a" / "b.bin", b"\x00\x01")

    assert path.read_bytes() == b"\x00\x01"


def test_save_response_uses_script_tool_and_category(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    script = tmp_path / "jobs" / "example" / "platform_tool.py"
    path = save_response(str(script), "platform", "list_projects_DEV", [{"Id": "1"}], timestamp_fmt="fixed")

    assert path == tmp_path / "output" / "platform_tool" / "platform" / "list_projects_DEV_fixed.json"
    assert json.loads(path.read_text(encoding="utf-8")) == [{"Id": "1"}]


def test_save_response_skips_empty_data(tmp_path):
    assert save_response(__file__, "platform", "projects", [], output_dir=tmp_path) is None
    assert list(tmp_path.iterdir()) == []


def test_save_response_group_prefix(tmp_path, monkeypatch):
    """传 group 时产物落 ``output/<分类>/<工具>[@env]/<子类别>``。"""
    monkeypatch.chdir(tmp_path)
    script = tmp_path / "jobs" / "platform" / "platform_tool.py"
    script.parent.mkdir(parents=True)
    script.touch()

    path = save_response(
        str(script), "platform", "x", {"a": 1}, group="platform", env="prod", timestamp_fmt="fixed"
    )

    assert path == tmp_path / "output" / "platform" / "platform_tool@prod" / "platform" / "x_fixed.json"


def test_save_response_env_suffixes_tool_dir(tmp_path, monkeypatch):
    """env 非 tst 时工具目录带 @{env} 后缀。"""
    monkeypatch.chdir(tmp_path)
    script = tmp_path / "jobs" / "example" / "platform_tool.py"
    script.parent.mkdir(parents=True)
    script.touch()

    path = save_response(str(script), "platform", "x", {"a": 1}, env="prod", timestamp_fmt="fixed")

    assert path == tmp_path / "output" / "platform_tool@prod" / "platform" / "x_fixed.json"


def test_setup_job_does_not_create_dir_before_log(tmp_path, monkeypatch):
    """import 期 setup_job(log_file=True) 不建目录，首次落日志才建。"""
    monkeypatch.chdir(tmp_path)
    script = tmp_path / "jobs" / "data_dev" / "test_script.py"
    script.parent.mkdir(parents=True)
    script.touch()

    setup_job(script, log_file=True)
    assert not (tmp_path / "output" / "logs").exists()


def test_setup_job(tmp_path, monkeypatch):
    """setup_job(log_file=True)：日志落在 <产物根>/output/logs/。"""
    monkeypatch.chdir(tmp_path)
    script = tmp_path / "jobs" / "data_dev" / "test_script.py"
    script.parent.mkdir(parents=True)
    script.touch()

    log = setup_job(script, log_file=True)
    assert log.name == "test_script"
    log.info("testing log output")

    out = tmp_path / "output" / "logs"
    assert len(list(out.glob("test_script_*.log"))) == 1


def test_set_log_env_is_idempotent(tmp_path, monkeypatch):
    """连续调用只保留最后一层 @env，不叠成 @prod@uat@prod。"""
    monkeypatch.chdir(tmp_path)
    script = tmp_path / "jobs" / "demo" / "demo_tool.py"
    script.parent.mkdir(parents=True)
    script.touch()
    root = logging.getLogger()
    saved = root.handlers[:]
    try:
        setup_job(str(script), log_file=True)
        today = datetime.now().strftime("%Y%m%d")
        logs = tmp_path / "output" / "logs"

        assert set_log_env("prod") == logs / f"demo_tool@prod_{today}.log"
        assert set_log_env("uat") == logs / f"demo_tool@uat_{today}.log"
        assert set_log_env("prod") == logs / f"demo_tool@prod_{today}.log"
        assert not list(logs.glob("demo_tool@*@*@*.log"))
    finally:
        _restore_root_handlers(root, saved)


def test_set_log_env_splits_log_file_by_env(tmp_path, monkeypatch):
    """非 tst（后缀小写）时 setup_job 的自动日志文件改名带 @env 后缀。"""
    monkeypatch.chdir(tmp_path)
    script = tmp_path / "jobs" / "demo" / "demo_tool.py"
    script.parent.mkdir(parents=True)
    script.touch()
    root = logging.getLogger()
    saved = root.handlers[:]
    try:
        setup_job(str(script), log_file=True)

        new_path = set_log_env("UAT")

        today = datetime.now().strftime("%Y%m%d")
        assert new_path == tmp_path / "output" / "logs" / f"demo_tool@uat_{today}.log"
        logging.getLogger("demo_tool").info("hello")
        assert new_path.exists()
        assert not (new_path.parent / f"demo_tool_{today}.log").exists()
    finally:
        _restore_root_handlers(root, saved)


def test_set_log_env_keeps_tst_log_file(tmp_path, monkeypatch):
    """tst（大小写不敏感）不改名，保持 <脚本名>_<YYYYMMDD>.log。"""
    monkeypatch.chdir(tmp_path)
    script = tmp_path / "jobs" / "demo" / "demo_tool.py"
    script.parent.mkdir(parents=True)
    script.touch()
    root = logging.getLogger()
    saved = root.handlers[:]
    try:
        setup_job(str(script), log_file=True)

        assert set_log_env("TST") is None

        today = datetime.now().strftime("%Y%m%d")
        logging.getLogger("demo_tool").info("hello")
        assert (tmp_path / "output" / "logs" / f"demo_tool_{today}.log").exists()
    finally:
        _restore_root_handlers(root, saved)


def _restore_root_handlers(root, saved):
    """摘掉测试装的 handler（先 close 防 Windows 文件占用），还原现场。"""
    for handler in root.handlers[:]:
        root.removeHandler(handler)
        handler.close()
    for handler in saved:
        root.addHandler(handler)
