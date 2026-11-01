"""终端输出工具：按显示宽度对齐的表格与目录树。"""

import unicodedata


def _display_width(s: str) -> int:
    """字符串显示宽度（中日韩 = 2，ASCII/box-drawing/emoji = 1）。"""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def _widths(headers: list[str], values: list[list[str]]) -> list[int]:
    """各列显示宽度：取表头与全部数据行的最大值。"""
    widths = [_display_width(h) for h in headers]
    for row in values:
        for i, v in enumerate(row):
            widths[i] = max(widths[i], _display_width(v))
    return widths


def _fmt_row(row: list[str], widths: list[int]) -> str:
    """按列宽补齐一行（中文算 2 宽，右侧补空格）。"""
    return " | ".join(v + " " * (widths[i] - _display_width(v)) for i, v in enumerate(row))


def print_table(headers: list[str], rows: list[list[object]], *, border: bool = False) -> None:
    """按显示宽度对齐输出表格（中文算2宽，ASCII算1宽）。

    版式：标题行下边一条 ``---+---`` 分隔线；``border=True`` 时表格最上与最下各加一条
    与行等宽的 ``--`` 线（默认不加，调用方按需开启）；``==`` 线留给调用方做汇总级分隔。

    Parameters
    ----------
    headers : list[str]
        表头。
    rows : list[list[object]]
        数据行；``None`` 显示为空串。
    border : bool, keyword-only
        是否加表格最上 / 最下的等宽边线，默认 ``False``（不加）。
    """
    values = [["" if v is None else str(v) for v in row] for row in rows]
    widths = _widths(headers, values)

    # 边线与 _fmt_row 行等宽：各列宽之和 + 列间 " | "（3 字符 × (列数-1)）
    edge = "-" * (sum(widths) + 3 * (len(widths) - 1))
    if border:
        print(edge)
    print(_fmt_row(headers, widths))
    print("-+-".join("-" * w for w in widths))
    for row in values:
        print(_fmt_row(row, widths))
    if border:
        print(edge)


def print_grouped_table(headers: list[str], groups: list[tuple[str, list[list[object]]]]) -> None:
    """多组数据合成**一张表**：单一表头 + 每组一行 ``▸ 组名`` 标记行。

    ``groups`` 为 ``[(组名, 行列表), ...]``，按传入顺序输出；组名行不占列宽，故表宽与
    :func:`print_table` 同口径（不新增列）。各组数据参与同一次列宽计算，跨组同名列对齐；
   计划表按目录分组时用它替代「每组一张表」，避免表头重复和组间错位。
    """
    blocks = [[["" if v is None else str(v) for v in row] for row in rows] for _, rows in groups]
    widths = _widths(headers, [row for block in blocks for row in block])
    print(_fmt_row(headers, widths))
    print("-+-".join("-" * w for w in widths))
    for (label, _), block in zip(groups, blocks):
        print(f"▸ {label}")
        for row in block:
            print(_fmt_row(row, widths))


def print_tree(
    items: list[dict],
    headers: list[str],
    *,
    parent_key: str = "Directory",
    name_key: str = "Name",
    container_type: str = "directory",
    type_key: str = "FileType",
    cols: list[str] | None = None,
):
    """按父子关系打印目录树，首列带树形缩进，其余列表格对齐。

    Parameters
    ----------
    items : list[dict]
        扁平条目列表。
    headers : list[str]
        表头（首列为名称列）。
    parent_key : str
        父路径字段名。
    name_key : str
        名称字段名。
    container_type : str
        容器类型标记值。
    type_key : str
        类型字段名。
    cols : list[str] | None
        各列对应的字段名；不传时取 headers 小写。
    """
    cols = cols or [h.lower() for h in headers]

    # 构建树（统一去掉尾斜杠，防止 API 返回的 "/视图登记/" 与拼接的 "/视图登记" 不匹配）
    tree: dict[str, list[dict]] = {}
    for f in items:
        parent = f.get(parent_key, "/").rstrip("/") or "/"
        tree.setdefault(parent, []).append(f)
    for parent in tree:
        tree[parent].sort(
            key=lambda f: (
                0 if f.get(type_key) == container_type else 1,
                (f.get(name_key) or "").lower(),
            )
        )

    # 收集展平行（首列带缩进）
    flat_rows: list[list[str]] = []

    def _collect(parent: str, indent: str = ""):
        children = tree.get(parent, [])
        for i, f in enumerate(children):
            is_last = i == len(children) - 1
            name = f.get(name_key, "")
            is_container = f.get(type_key) == container_type
            tag = "📁 " if is_container else "📄 "
            stem = "└── " if is_last else "├── "
            ext = "    " if is_last else "│   "
            row = [indent + stem + tag + name]
            for c in cols[1:]:
                row.append(str(f.get(c, "")) if f.get(c) is not None else "")
            flat_rows.append(row)
            if is_container:
                child_path = (parent.rstrip("/") + "/" + name).replace("//", "/")
                _collect(child_path, indent + ext)

    _collect("/")

    widths = [_display_width(h) for h in headers]
    for row in flat_rows:
        for i, v in enumerate(row):
            widths[i] = max(widths[i], _display_width(v))

    def _fmt(row: list[str]) -> str:
        return " | ".join(v + " " * (widths[i] - _display_width(v)) for i, v in enumerate(row))

    print(_fmt(headers))
    print("-+-".join("-" * w for w in widths))
    for row in flat_rows:
        print(_fmt(row))
