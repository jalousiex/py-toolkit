"""命令行辅助：分组子命令帮助与参数回退顺序。"""

import argparse

import pytest

from small_toolkit import add_grouped_subparsers, add_parameter, resolve_env_var, resolve_parameters


def test_add_grouped_subparsers_formats_groups_and_footer():
    parser = argparse.ArgumentParser(description="示例工具")
    commands = add_grouped_subparsers(
        parser,
        {
            "查询": [("list", "列出任务"), ("info", "查看详情")],
            "变更": [("submit", "提交草稿")],
        },
        footer="写操作默认 dry-run。",
    )

    help_text = parser.format_help()

    assert list(commands) == ["list", "info", "submit"]
    assert "写操作默认 dry-run。" in help_text


def test_add_grouped_subparsers_rejects_empty_groups():
    parser = argparse.ArgumentParser()

    with pytest.raises(ValueError, match="命令分组不能为空"):
        add_grouped_subparsers(parser, {})


def test_add_parameter_requires_long_option():
    parser = argparse.ArgumentParser()

    with pytest.raises(ValueError, match="必须使用长选项"):
        add_parameter(parser, "-d")


def test_add_parameter_rejects_duplicate():
    parser = argparse.ArgumentParser()
    add_parameter(parser, "--database")

    with pytest.raises(ValueError, match="重复的参数配置"):
        add_parameter(parser, "--database")


def test_resolve_parameters_cli_wins_over_env_and_default(monkeypatch):
    monkeypatch.setenv("TOOLKIT_TEST_DB", "envdb")
    parser = argparse.ArgumentParser()
    add_parameter(parser, "--database", env="TOOLKIT_TEST_DB", default="fallback")

    args = resolve_parameters(parser.parse_args(["--database", "clidb"]))

    assert args.database == "clidb"


def test_resolve_parameters_falls_back_to_env_then_default(monkeypatch):
    monkeypatch.setenv("TOOLKIT_TEST_DB", "envdb")
    parser = argparse.ArgumentParser()
    add_parameter(parser, "--database", env="TOOLKIT_TEST_DB", default="fallback")
    assert resolve_parameters(parser.parse_args([])).database == "envdb"

    monkeypatch.delenv("TOOLKIT_TEST_DB")
    assert resolve_parameters(parser.parse_args([])).database == "fallback"


def test_resolve_parameters_treats_placeholder_as_unset(monkeypatch):
    """平台占位符 ``${name}`` 视为未设置，回退到环境变量。"""
    monkeypatch.setenv("TOOLKIT_TEST_DB", "envdb")
    parser = argparse.ArgumentParser()
    add_parameter(parser, "--database", env="TOOLKIT_TEST_DB", parameter="${database}")

    assert resolve_parameters(parser.parse_args([])).database == "envdb"


def test_resolve_parameters_casts_string_by_type(monkeypatch):
    parser = argparse.ArgumentParser()
    add_parameter(parser, "--port", env="TOOLKIT_TEST_PORT", default=8080, type=int)
    monkeypatch.setenv("TOOLKIT_TEST_PORT", "9000")

    assert resolve_parameters(parser.parse_args([])).port == 9000


def test_resolve_env_var_reads_list_first(monkeypatch):
    monkeypatch.setenv("TOOLKIT_TEST_URL_LIST", "tst=a:8030;prod=b:8030")
    monkeypatch.setenv("TOOLKIT_TEST_URL_TST", "single")

    assert resolve_env_var("tst", "TOOLKIT_TEST_URL") == "a:8030"


def test_resolve_env_var_prefers_single_env_then_native_for_prod(monkeypatch):
    monkeypatch.setenv("TOOLKIT_TEST_URL", "native")
    assert resolve_env_var("prod", "TOOLKIT_TEST_URL") == "native"
    # 非 prod 环境不读原生变量
    assert resolve_env_var("uat", "TOOLKIT_TEST_URL") is None


def test_resolve_env_var_missing_returns_none(monkeypatch):
    monkeypatch.delenv("TOOLKIT_TEST_URL", raising=False)
    monkeypatch.delenv("TOOLKIT_TEST_URL_LIST", raising=False)

    assert resolve_env_var("tst", "TOOLKIT_TEST_URL") is None
