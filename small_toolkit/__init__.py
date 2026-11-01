"""small_toolkit：纯标准库的通用小工具（产物目录 / 日志 / 命令行 / 终端表格）。

分区：:mod:`small_toolkit.outputs` 路径与落盘、:mod:`small_toolkit.logs` 日志初始化、
:mod:`small_toolkit.cli` 命令行参数、:mod:`small_toolkit.table` 终端表格。全部零第三方依赖、
不读凭据、不含内网地址。
"""

from .cli import (
    add_grouped_subparsers,
    add_parameter,
    resolve_env_var,
    resolve_parameters,
)
from .logs import (
    DEBUG_HELP,
    add_debug_argument,
    enable_debug_logging,
    set_log_env,
    setup_job,
)
from .outputs import (
    WORKSPACE_MARKERS,
    display_path,
    env_suffix,
    get_output_dir,
    output_dir,
    output_root,
    save_bytes,
    save_json,
    save_response,
    tool_dir_name,
    tool_output_dir,
    write_json,
)
from .table import print_grouped_table, print_table, print_tree

__all__ = [
    "DEBUG_HELP",
    "WORKSPACE_MARKERS",
    "add_debug_argument",
    "add_grouped_subparsers",
    "add_parameter",
    "display_path",
    "enable_debug_logging",
    "env_suffix",
    "get_output_dir",
    "output_dir",
    "output_root",
    "print_grouped_table",
    "print_table",
    "print_tree",
    "resolve_env_var",
    "resolve_parameters",
    "save_bytes",
    "save_json",
    "save_response",
    "set_log_env",
    "setup_job",
    "tool_dir_name",
    "tool_output_dir",
    "write_json",
]
