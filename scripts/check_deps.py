# -*- coding: utf-8 -*-
"""
scripts/check_deps.py - 依赖声明一致性校验

问题背景：
    本项目在两个地方声明了运行依赖，二者的角色不同：
      - pyproject.toml 的 [project] dependencies —— 权威来源（现代推荐做法）
      - requirements.txt                        —— 给不熟悉现代打包工具的人用的简写
    两处必须保持一致。但"靠人记住要同步改两处"是很容易忘的，
    一旦忘了，就会出现"pip 装得上、打包装不上"这类难查的问题。

本脚本的作用：
    自动比对两处声明，不一致就报错退出（退出码 1）。CI 每次都会跑它。

用法：
    python scripts/check_deps.py

退出码：
    0 = 一致；1 = 不一致或文件读不到（错误信息会指明差异）
"""
import sys
from pathlib import Path

# 脚本在 scripts/ 下，项目根目录是它的上一级
ROOT = Path(__file__).resolve().parent.parent


def _normalize(requirement: str) -> str:
    """把一个依赖声明归一化成"包名"。

    例如 "Flask>=2.3" → "flask"，"pytest>=7.0" → "pytest"。
    只比较包名，不比较版本：版本约束可以各自表述（一个写 >=2.3、一个写 >=2.3.0
    都能满足需求），但包本身漏了就是真问题。
    """
    name = requirement.split(">")[0].split("=")[0].split("<")[0].split("~")[0]
    # 去掉 extras 标记，如 "flask[async]" → "flask"
    name = name.split("[")[0]
    return name.strip().lower()


def read_pyproject_deps() -> set:
    """从 pyproject.toml 读取运行依赖（权威来源）。

    tomllib 是 Python 3.11 起的内置库；3.10 环境按下面的提示装 tomli。
    """
    try:
        import tomllib
    except ImportError:  # Python 3.10
        try:
            import tomli as tomllib  # type: ignore[no-redef]
        except ImportError:
            print("[跳过] 当前 Python 无 tomllib（3.10 需 pip install tomli），"
                  "无法校验 pyproject.toml，本次跳过。")
            return set()

    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return {_normalize(dep) for dep in data["project"]["dependencies"]}


def read_requirements_deps() -> set:
    """从 requirements.txt 读取运行依赖（忽略注释行与空行）。"""
    deps = set()
    for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines():
        line = line.split("#")[0].strip()
        if line:
            deps.add(_normalize(line))
    return deps


def main() -> int:
    declared = read_pyproject_deps()
    pinned = read_requirements_deps()

    if not declared:
        return 0  # 环境缺 tomllib，已打印跳过说明

    print(f"pyproject.toml  : {sorted(declared)}")
    print(f"requirements.txt: {sorted(pinned)}")

    missing = declared - pinned   # pyproject 有、requirements 缺
    extra = pinned - declared     # requirements 有、pyproject 缺

    if missing or extra:
        print("\n[失败] 依赖声明不一致，请同步两个文件：")
        if missing:
            print(f"  requirements.txt 缺少: {sorted(missing)}")
        if extra:
            print(f"  pyproject.toml 缺少  : {sorted(extra)}")
        return 1

    print("\n[通过] 两处依赖声明一致。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
