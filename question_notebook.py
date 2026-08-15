# -*- coding: utf-8 -*-
"""
question_notebook.py - CLI 界面层

负责命令行交互（菜单、输入输出），数据逻辑由 models.py 提供。
运行：python question_notebook.py
"""
import datetime
import os

from models import (
    Question,
    load_questions,
    save_questions,
    build_csv,
    backup_data,
    list_backups,
    restore_data,
    DATA_FILE,
    BACKUP_DIR,
    EXPORT_DIR,
    DEFAULT_CATEGORY,
)


def print_questions(questions, header, empty_msg="当前空空如也，快去添加第一个问题吧！"):
    """格式化输出问题列表（查看全部/筛选/分类查看共用）。"""
    print(f"\n{header}")

    if not questions:
        print(empty_msg)
        return

    for q in questions:
        status = "已解决" if q.is_solved else "未解决"
        print(f"[{q.id}] {q.title}  | 分类: {q.category}  | 状态: {status}  | 时间: {q.timestamp}")
        if q.description:
            print(f"描述: {q.description}")
        if q.is_solved and q.solution:
            print(f"方案: {q.solution}")
        print("-" * 40)


def add_question(questions):
    """交互式添加新问题并保存。"""
    print("\n--- 添加新问题 ---")

    title = input("请输入问题标题: ")

    # 标题为空或全为空格时取消添加
    if not title.strip():
        print("标题不能为空，取消添加。")
        return

    description = input("请输入问题详细描述 (可选，直接按回车跳过): ")
    category = input(f"请输入分类 (可选，直接回车默认为'{DEFAULT_CATEGORY}'): ").strip()
    if not category:
        category = DEFAULT_CATEGORY

    new_q = Question(title=title, description=description, category=category)
    questions.append(new_q)
    save_questions(questions)
    print(f"问题 '{title}' 已成功添加并保存！")


def list_questions(questions):
    """输出全部问题。"""
    print_questions(questions, "--- 我的问题笔记本 ---")


def solve_question(questions):
    """将指定 ID 的问题标记为已解决，并记录解决方案。"""
    print("\n--- [!] 标记问题为已解决 ---")
    try:
        q_id = int(input("请输入要解决的问题ID: "))
    except ValueError:
        print("[错误] ID必须是数字！")
        return

    # 按 ID 查找目标问题
    target_q = None
    for q in questions:
        if q.id == q_id:
            target_q = q
            break

    if target_q is None:
        print(f"[错误] 未找到ID为 {q_id} 的问题。")
        return

    if target_q.is_solved:
        print(f"[提示] 问题 '{target_q.title}' 已经是已解决状态了。")
        return

    solution = input("请输入解决方案/心得: ")
    target_q.is_solved = True
    target_q.solution = solution

    save_questions(questions)
    print(f"[成功] 问题 '{target_q.title}' 已标记为已解决！")


def delete_question(questions):
    """按 ID 删除问题（需二次确认）。"""
    print("\n--- [x] 删除问题 ---")
    try:
        q_id = int(input("请输入要删除的问题ID: "))
    except ValueError:
        print("[错误] ID必须是数字！")
        return

    # 确认目标问题存在
    target_q = None
    for q in questions:
        if q.id == q_id:
            target_q = q
            break

    if target_q is None:
        print(f"[错误] 未找到ID为 {q_id} 的问题，删除失败。")
        return

    # 二次确认，防止误删
    confirm = input(f"确认删除问题 '{target_q.title}' (ID: {q_id}) 吗？(y/N): ").strip().lower()
    if confirm != 'y':
        print("[提示] 已取消删除。")
        return

    # 列表推导式过滤目标 ID（比直接 remove 更安全）
    original_len = len(questions)
    questions[:] = [q for q in questions if q.id != q_id]

    if len(questions) < original_len:
        save_questions(questions)
        print(f"[成功] ID为 {q_id} 的问题已被永久删除。")


def search_questions(questions):
    """关键词搜索（忽略大小写，匹配标题/描述/方案/分类）。

    支持空格分隔多个关键词，全部命中才算匹配（如：python 报错）。
    """
    print("\n--- [?] 搜索问题 ---")
    keyword = input("请输入搜索关键词 (多个词用空格分隔，如: python 报错): ").strip()

    if not keyword:
        print("[提示] 关键词不能为空。")
        return

    # 拆分关键词并统一小写
    keywords = [k.lower() for k in keyword.split()]
    results = []

    for q in questions:
        # 拼接全部可搜索文本并统一小写
        searchable_text = " ".join([
            q.title,
            q.description or "",
            q.solution or "",
            q.category or ""
        ]).lower()

        # AND 逻辑：所有关键词都必须命中
        if all(k in searchable_text for k in keywords):
            results.append(q)

    if not results:
        print(f"[结果] 没有找到同时包含 {keywords} 的问题。")
    else:
        print(f"[结果] 找到 {len(results)} 个匹配的问题：")
        for q in results:
            status = "[已解决]" if q.is_solved else "[未解决]"
            print(f"  - [{q.id}] {q.title} ({q.category}) {status}")


def edit_question(questions):
    """按 ID 编辑问题（可修改标题/描述/分类/解决方案，回车表示该项保持不变）。"""
    print("\n--- [e] 编辑问题 ---")
    try:
        q_id = int(input("请输入要编辑的问题ID: "))
    except ValueError:
        print("[错误] ID必须是数字！")
        return

    # 按 ID 查找目标问题
    target_q = None
    for q in questions:
        if q.id == q_id:
            target_q = q
            break

    if target_q is None:
        print(f"[错误] 未找到ID为 {q_id} 的问题。")
        return

    old_title = target_q.title

    print(f"当前标题: {target_q.title}")
    new_title = input("请输入新标题 (直接回车保持不变): ").strip()
    if new_title:
        target_q.title = new_title

    print(f"当前描述: {target_q.description or '(空)'}")
    new_desc = input("请输入新描述 (直接回车保持不变): ").strip()
    if new_desc:
        target_q.description = new_desc

    print(f"当前分类: {target_q.category}")
    new_category = input("请输入新分类 (直接回车保持不变): ").strip()
    if new_category:
        target_q.category = new_category

    if target_q.is_solved:
        print(f"当前解决方案: {target_q.solution or '(空)'}")
        new_solution = input("请输入新解决方案 (直接回车保持不变): ").strip()
        if new_solution:
            target_q.solution = new_solution

    save_questions(questions)
    print(f"[成功] 问题 '{old_title}' 已更新为 '{target_q.title}'！")


def filter_questions(questions):
    """按解决状态筛选问题。"""
    print("\n--- [f] 按状态筛选 ---")
    print("  1. 只看未解决")
    print("  2. 只看已解决")
    print("  0. 返回主菜单")
    choice = input(">> 请选择: ").strip()

    if choice == '1':
        filtered = [q for q in questions if not q.is_solved]
        print_questions(filtered, "--- 未解决的问题 ---", "太棒了，没有未解决的问题！")
    elif choice == '2':
        filtered = [q for q in questions if q.is_solved]
        print_questions(filtered, "--- 已解决的问题 ---", "还没有已解决的问题，加油！")
    elif choice == '0':
        return
    else:
        print("[警告] 无效输入。")


def backup_questions():
    """将当前数据文件备份到 backups/ 目录（带时间戳，由数据层处理）。"""
    print("\n--- [b] 备份数据 ---")
    name = backup_data()
    if name is None:
        print("[提示] 还没有数据文件，无需备份。")
        return
    print(f"[成功] 已备份到 {os.path.join(BACKUP_DIR, name)}")


def restore_questions(questions):
    """从备份文件恢复数据（覆盖当前数据前二次确认）。"""
    print("\n--- [r] 恢复数据 ---")
    # 列出所有备份文件，新的在前（数据层统一逻辑）
    backups = list_backups()
    if not backups:
        print("[提示] 还没有任何备份。")
        return

    print("可用的备份：")
    for i, name in enumerate(backups, 1):
        print(f"  {i}. {name}")

    try:
        choice = int(input("请输入要恢复的备份编号 (0 取消): "))
    except ValueError:
        print("[错误] 编号必须是数字！")
        return

    if choice == 0:
        print("[提示] 已取消恢复。")
        return
    if choice < 1 or choice > len(backups):
        print("[错误] 无效的备份编号。")
        return

    backup_name = backups[choice - 1]
    confirm = input(f"恢复将覆盖当前全部数据，确认从 {backup_name} 恢复吗？(y/N): ").strip().lower()
    if confirm != 'y':
        print("[提示] 已取消恢复。")
        return

    # 数据层执行恢复（含文件名白名单校验），成功后在内存中重新加载
    if not restore_data(backup_name):
        print("[错误] 恢复失败，备份文件无效。")
        return
    questions.clear()
    questions.extend(load_questions())
    print(f"[成功] 数据已恢复！共 {len(questions)} 条问题。")


def backup_menu(questions):
    """备份与恢复子菜单。"""
    while True:
        print("\n--- 备份与恢复 ---")
        print("  1. 备份当前数据")
        print("  2. 从备份恢复")
        print("  0. 返回主菜单")
        choice = input(">> 请选择: ").strip()

        if choice == '1':
            backup_questions()
        elif choice == '2':
            restore_questions(questions)
        elif choice == '0':
            return
        else:
            print("[警告] 无效输入。")


def export_csv(questions):
    """导出问题列表为 CSV 文件（UTF-8 BOM，Excel 直接打开不乱码）。"""
    print("\n--- [c] 导出 CSV ---")

    if not questions:
        print("[提示] 当前没有数据可导出。")
        return

    os.makedirs(EXPORT_DIR, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    export_path = os.path.join(EXPORT_DIR, f"questions_{timestamp}.csv")

    # 内容由数据层生成（含 BOM 头），界面层只负责写文件
    with open(export_path, 'w', encoding='utf-8', newline='') as file:
        file.write(build_csv(questions))

    print(f"[成功] 已导出 {len(questions)} 条问题到 {export_path}")


def view_by_category(questions):
    """按分类查看问题。"""
    print("\n--- [g] 按分类查看 ---")

    if not questions:
        print("[提示] 当前没有数据。")
        return

    # 收集全部分类（去重，保持出现顺序）
    categories = []
    for q in questions:
        if q.category not in categories:
            categories.append(q.category)

    print("现有分类：")
    for i, cat in enumerate(categories, 1):
        count = sum(1 for q in questions if q.category == cat)
        print(f"  {i}. {cat} ({count} 条)")
    print("  0. 返回主菜单")

    choice = input(">> 请选择分类编号: ").strip()
    if choice == '0':
        return

    try:
        idx = int(choice)
    except ValueError:
        print("[错误] 请输入数字编号。")
        return

    if idx < 1 or idx > len(categories):
        print("[错误] 无效的分类编号。")
        return

    selected = categories[idx - 1]
    filtered = [q for q in questions if q.category == selected]
    print_questions(filtered, f"--- 分类「{selected}」的问题 ---", f"分类「{selected}」下暂时没有问题。")


def main():
    """程序入口：加载数据，进入菜单循环。"""
    # 从数据层加载（文件不存在时给出提示，不报错）
    if os.path.exists(DATA_FILE):
        questions = load_questions()
        print(f"成功从 {DATA_FILE} 加载了 {len(questions)} 个问题。")
    else:
        questions = []
        print(f"数据文件 {DATA_FILE} 不存在，将创建一个新的文件。")

    while True:
        print("\n=========================")
        print("     问题笔记本主菜单")
        print("=========================")
        print("  1. 查看所有问题")
        print("  2. 添加新问题")
        print("  3. 标记问题为已解决")
        print("  4. 删除问题")
        print("  5. 搜索问题")
        print("  6. 编辑问题")
        print("  7. 备份与恢复")
        print("  8. 按状态筛选")
        print("  9. 导出 CSV")
        print("  10. 按分类查看")
        print("  0. 退出程序")
        print("=========================")

        choice = input(">> 请输入选项编号: ")

        if choice == '1':
            list_questions(questions)
        elif choice == '2':
            add_question(questions)
        elif choice == '3':
            solve_question(questions)
        elif choice == '4':
            delete_question(questions)
        elif choice == '5':
            search_questions(questions)
        elif choice == '6':
            edit_question(questions)
        elif choice == '7':
            backup_menu(questions)
        elif choice == '8':
            filter_questions(questions)
        elif choice == '9':
            export_csv(questions)
        elif choice == '10':
            view_by_category(questions)
        elif choice == '0':
            print("感谢使用，再见！")
            break
        else:
            print("[警告] 无效输入，请输入 0-10 之间的数字。")


if __name__ == "__main__":
    main()
