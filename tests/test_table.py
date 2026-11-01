"""终端表格输出：对齐宽度与上下边线开关。"""

from small_toolkit import print_grouped_table, print_table


def _capture(capsys, headers, rows, **kwargs):
    print_table(headers, rows, **kwargs)
    return capsys.readouterr().out.splitlines()


def test_default_has_no_top_or_bottom_border(capsys):
    """默认不加边线：标题行上边无 ``--`` 线、末行下边也无。"""
    lines = _capture(capsys, ["ID", "名称"], [["1", "项目甲"]])

    # 列宽：ID=2、名称=max(4, 6)=6（中文算 2 宽）；表头按列宽右补空格
    assert lines[0] == "ID | 名称  "
    assert lines[1] == "---+-------"
    assert not lines[-1].startswith("---")


def test_border_adds_equal_width_top_and_bottom_lines(capsys):
    """border=True：表格最上与最下各一条等宽 ``--`` 线。"""
    lines = _capture(capsys, ["ID", "名称"], [["1", "项目甲"], ["22", "乙"]], border=True)

    # 等宽于表格行：列宽 2/6 + 列间 " | "（3 字符）= 11
    edge = "-" * 11
    assert lines[0] == edge
    assert lines[1] == "ID | 名称  "
    assert lines[-1] == edge


def test_none_cell_renders_empty(capsys):
    """None 单元格显示为空串，不炸宽度计算。"""
    lines = _capture(capsys, ["ID", "名称"], [[None, None]])

    # 列宽取表头：ID=2、名称=4
    assert lines[2] == " " * 2 + " | " + " " * 4


def test_grouped_table_merges_groups_under_one_header(capsys):
    """多组合成一张表：表头只出一次、每组一行 ``▸`` 标记，列宽按全量数据统一。"""
    groups = [("/A", [["1", "x"]]), ("/BB", [["2", "yyy"]])]
    print_grouped_table(["ID", "名称"], groups)
    lines = capsys.readouterr().out.splitlines()

    # 列宽取全量：ID=2、名称=max(4, 1, 3)=4，两组行同宽
    assert lines[0] == "ID | 名称"
    assert lines[1] == "---+-----"
    assert lines[2:] == ["▸ /A", "1  | x   ", "▸ /BB", "2  | yyy "]
