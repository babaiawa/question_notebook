# -*- coding: utf-8 -*-
"""
scripts/check_version.py - 版本号一致性校验

问题背景：
    项目里"版本号"有**两个权威位置**，它们必须相等：
      - pyproject.toml 的 [project] version  —— 打包元数据（别人 pip 安装时看到的版本）
      - src/question_notebook/__init__.py 的 __version__  —— 程序运行时能读到的版本
    两处不一致会导致很隐蔽的怪事：安装信息显示 0.3.0，程序里却报 0.2.1，
    排查时极难想到是"两个地方各写了一个版本"。

    （文档里也会提到版本号，但那些是**说明性文字**，不是权威值；本脚本只校验
      上面两处权威来源，避免把文档改字也变成构建失败。）

本脚本的作用：
    读取两处版本并比对，不一致就报错退出（退出码 1）。CI 每次都会跑它。

用法：
    python scripts/check_version.py
    python scripts/check_version.py --show   # 额外列出文档中提到该版本的位置（仅供参考）

退出码：
    0 = 一致；1 = 不一致或读不到版本号
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"
INIT_PY = ROOT / "src" / "question_notebook" / "__init__.py"


def read_pyproject_version():
    """从 pyproject.toml 读版本号。

    用 tomllib（Python 3.11+ 内置）解析，保证读的是真正的字段而不是正则碰巧匹配到
    某句注释。Python 3.10 没有 tomllib，退回正则提取（此时会提示说明）。
    """
    text = PYPROJECT.read_text(encoding="utf-8")
    try:
        import tomllib
    except ImportError:  # Python 3.10
        m = re.search(r'(?m)^\s*version\s*=\s*["\']([^"\']+)["\']', text)
        return m.group(1) if m else None
    try:
        return tomllib.loads(text)["project"]["version"]
    except (KeyError, ValueError):
        return None


def read_package_version():
    """从包的 __init__.py 读 __version__。

    刻意用正则读文本、而不是 `import question_notebook` 后取属性：
    这样脚本无需安装本项目、也不必处理 sys.path，任何环境都能跑。
    """
    text = INIT_PY.read_text(encoding="utf-8")
    m = re.search(r'(?m)^__version__\s*=\s*["\']([^"\']+)["\']', text)
    return m.group(1) if m else None


def find_doc_mentions(version):
    """列出文档中提到该版本号的文件与次数（仅供参考，不参与判定）。"""
    hits = []
    for path in sorted(ROOT.glob("*.md")):
        n = len(re.findall(re.escape(version), path.read_text(encoding="utf-8")))
        if n:
            hits.append((path.name, n))
    return hits


def main() -> int:
    show = "--show" in sys.argv

    pyproject_version = read_pyproject_version()
    package_version = read_package_version()

    print(f"pyproject.toml 的 version        : {pyproject_version}")
    print(f"question_notebook.__version__    : {package_version}")

    if not pyproject_version:
        print(f"\n[失败] 未能从 {PYPROJECT.name} 读到 [project] version。")
        return 1
    if not package_version:
        print(f"\n[失败] 未能从 {INIT_PY.relative_to(ROOT)} 读到 __version__。")
        return 1

    if pyproject_version != package_version:
        print("\n[失败] 两处版本号不一致！请把它们改成同一个值：")
        print(f"  {PYPROJECT.relative_to(ROOT)}  →  version = \"{pyproject_version}\"")
        print(f"  {INIT_PY.relative_to(ROOT)}  →  __version__ = \"{package_version}\"")
        print("\n改版本号时建议同时更新 README 的更新日志与 ROADMAP（见 STANDARDS.md 第 7 节）。")
        return 1

    print(f"\n[通过] 两处版本号一致：{pyproject_version}")

    if show:
        mentions = find_doc_mentions(pyproject_version)
        if mentions:
            print("\n文档中提到该版本号的位置（说明性文字，仅提示，不算错误）：")
            for name, n in mentions:
                print(f"  {name}  {n} 处")
    return 0


if __name__ == "__main__":
    sys.exit(main())
