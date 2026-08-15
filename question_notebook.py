import json
import datetime
import os
import shutil

# 基于脚本所在目录定位数据文件，避免从其他目录运行时跑偏
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "questions.json")
BACKUP_DIR = os.path.join(BASE_DIR, "backups")
DEFAULT_CATEGORY = "未分类"

class Question:
    """这是一个用来存储问题的类。包含问题的标题、描述、解决状态、解决方案、分类以及创建时间等相关信息。"""
    def __init__(self, title, description="", is_solved=False, solution="", category=DEFAULT_CATEGORY):
        self.id = None  # 程序内部自动生成
        self.title = title
        self.description = description
        self.timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.is_solved = is_solved
        self.solution = solution
        self.category = category

def save_questions(questions):
    """将问题对象列表保存到JSON文件中。"""
    
    # 1. 找出当前最大的 ID，以便为新问题生成下一个 ID
    # 如果列表为空，最大 ID 就是 0
    max_id = 0
    for q in questions:
        if q.id is not None and q.id > max_id:
            max_id = q.id

    # 2. 将 Question 对象列表转换成字典列表
    questions_as_dicts = []
    for q in questions:
        # 如果这个问题还没有 ID（说明是新添加的），就给它分配一个
        if q.id is None:
            max_id += 1
            q.id = max_id
            
        # 把对象的属性提取出来，做成一个字典
        q_dict = {
            "id": q.id,
            "title": q.title,
            "description": q.description,
            "timestamp": q.timestamp,
            "is_solved": q.is_solved,
            "solution": q.solution,
            "category": q.category
        }
        questions_as_dicts.append(q_dict)

    # 3. 将字典列表写入文件
    with open(DATA_FILE, 'w', encoding='utf-8') as file:
        json.dump(questions_as_dicts, file, indent=4, ensure_ascii=False)
    
    print("问题列表已成功保存！")

def load_questions():
    """从JSON文件中加载问题列表。如果文件不存在，则返回一个空列表。"""
    try:
        # 尝试打开文件
        with open(DATA_FILE, 'r', encoding='utf-8') as file:
            # 读取JSON数据
            data = json.load(file)
            
            questions = []
            for item in data:
                # get() 带默认值：兼容旧数据（没有 category 字段时补"未分类"）
                q = Question(
                    title=item['title'],
                    description=item.get('description', ''),
                    is_solved=item.get('is_solved', False),
                    solution=item.get('solution', ''),
                    category=item.get('category', DEFAULT_CATEGORY)
                )
                q.id = item['id']
                q.timestamp = item.get('timestamp', '')
                questions.append(q)
            
            print(f"成功从 {DATA_FILE} 加载了 {len(questions)} 个问题。")
            return questions
            
    except FileNotFoundError:
        # 如果文件不存在，我们捕获这个异常，并返回一个空列表
        print(f"数据文件 {DATA_FILE} 不存在，将创建一个新的文件。")
        return []
    except json.JSONDecodeError:
        # JSON 文件损坏时，备份原文件后返回空列表，避免程序崩溃
        backup_file = DATA_FILE + ".bak"
        try:
            os.replace(DATA_FILE, backup_file)
            print(f"[警告] 数据文件损坏，已备份到 {backup_file}，将创建一个新的文件。")
        except OSError:
            print("[警告] 数据文件损坏且无法备份，将创建一个新的文件。")
        return []

def print_questions(questions, header, empty_msg="当前空空如也，快去添加第一个问题吧！"):
    """格式化打印问题列表（查看全部/筛选共用）。"""
    print(f"\n{header}")
    
    # 如果列表为空，给出提示
    if not questions:
        print(empty_msg)
        return
        
    # 遍历列表，打印每个问题的信息
    for q in questions:
        # 使用三元表达式（类似 C 语言的 ? : ）来决定显示的状态图标
        status = "已解决" if q.is_solved else "未解决"
        
        print(f"[{q.id}] {q.title}  | 分类: {q.category}  | 状态: {status}  | 时间: {q.timestamp}")
        if q.description:
            print(f"描述: {q.description}")
        if q.is_solved and q.solution:
            print(f"方案: {q.solution}")
        print("-" * 40) # 打印分割线

def add_question(questions):
    """提示用户输入信息，创建新问题并保存。"""
    print("\n--- 添加新问题 ---")
    
    # input() 函数相当于 C 语言里的 scanf 或gets，用来获取用户的键盘输入
    title = input("请输入问题标题: ")
    
    # 简单的数据校验：如果标题全是空格或为空，则取消添加
    if not title.strip():
        print("标题不能为空，取消添加。")
        return
        
    description = input("请输入问题详细描述 (可选，直接按回车跳过): ")
    category = input(f"请输入分类 (可选，直接回车默认为'{DEFAULT_CATEGORY}'): ").strip()
    if not category:
        category = DEFAULT_CATEGORY
    
    # 使用收集到的信息创建 Question 对象
    new_q = Question(title=title, description=description, category=category)
    
    # 将新问题加入到列表中
    questions.append(new_q)
    
    # 调用我们之前写好的保存函数
    save_questions(questions)
    print(f"问题 '{title}' 已成功添加并保存！")

def list_questions(questions):
    """格式化打印出所有的问题。"""
    print_questions(questions, "--- 我的问题笔记本 ---")

def solve_question(questions):
    """将指定ID的问题标记为已解决，并添加解决方案。"""
    print("\n--- [!] 标记问题为已解决 ---")
    try:
        q_id = int(input("请输入要解决的问题ID: "))
    except ValueError:
        print("[错误] ID必须是数字！")
        return

    # 查找对应ID的问题
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
    """根据ID删除指定的问题。"""
    print("\n--- [x] 删除问题 ---")
    try:
        q_id = int(input("请输入要删除的问题ID: "))
    except ValueError:
        print("[错误] ID必须是数字！")
        return

    # 先确认目标问题是否存在
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

    # 使用列表推导式过滤掉目标ID（比直接remove更安全）
    original_len = len(questions)
    questions[:] = [q for q in questions if q.id != q_id]

    if len(questions) < original_len:
        save_questions(questions)
        print(f"[成功] ID为 {q_id} 的问题已被永久删除。")

def search_questions(questions):
    """根据关键词搜索问题（忽略大小写，匹配标题/描述/方案/分类）。"""
    print("\n--- [?] 搜索问题 ---")
    keyword = input("请输入搜索关键词: ").strip()
    
    if not keyword:
        print("[提示] 关键词不能为空。")
        return
        
    # 将搜索词统一转为小写
    keyword_lower = keyword.lower()
    results = []
    
    # 遍历所有问题进行比对
    for q in questions:
        # 将目标文本也转为小写，然后用 in 判断是否包含
        title_match = keyword_lower in q.title.lower()
        
        # 如果描述、方案或分类为空，直接设为 False，防止报错
        desc_match = keyword_lower in q.description.lower() if q.description else False
        sol_match = keyword_lower in q.solution.lower() if q.solution else False
        cat_match = keyword_lower in q.category.lower() if q.category else False
        
        # 标题、描述、方案、分类中有任何一个匹配就加入结果列表
        if title_match or desc_match or sol_match or cat_match:
            results.append(q)
            
    # 打印搜索结果
    if not results:
        print(f"[结果] 没有找到包含 '{keyword}' 的问题。")
    else:
        print(f"[结果] 找到 {len(results)} 个匹配的问题：")
        for q in results:
            status = "[已解决]" if q.is_solved else "[未解决]"
            print(f"  - [{q.id}] {q.title} ({q.category}) {status}")

def edit_question(questions):
    """根据ID编辑问题，可修改标题、描述、分类和解决方案（直接回车表示该项保持不变）。"""
    print("\n--- [e] 编辑问题 ---")
    try:
        q_id = int(input("请输入要编辑的问题ID: "))
    except ValueError:
        print("[错误] ID必须是数字！")
        return

    # 查找对应ID的问题
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
    """按解决状态筛选问题（只看未解决/已解决）。"""
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
    """将当前数据文件备份到 backups/ 目录（带时间戳）。"""
    print("\n--- [b] 备份数据 ---")
    if not os.path.exists(DATA_FILE):
        print("[提示] 还没有数据文件，无需备份。")
        return
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"questions_{timestamp}.json")
    shutil.copy2(DATA_FILE, backup_path)
    print(f"[成功] 已备份到 {backup_path}")

def restore_questions(questions):
    """从备份文件恢复数据（覆盖当前数据前二次确认）。"""
    print("\n--- [r] 恢复数据 ---")
    if not os.path.isdir(BACKUP_DIR):
        print("[提示] 还没有任何备份。")
        return
    
    # 列出所有备份文件，新的在前
    backups = sorted(
        [f for f in os.listdir(BACKUP_DIR) if f.startswith("questions_") and f.endswith(".json")],
        reverse=True
    )
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
    
    # 覆盖数据文件并重新加载到内存
    shutil.copy2(os.path.join(BACKUP_DIR, backup_name), DATA_FILE)
    questions.clear()
    questions.extend(load_questions())
    print("[成功] 数据已恢复！")

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

def main():
    """程序的主入口，负责显示菜单和处理用户交互。"""
    questions = load_questions()
    
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
        elif choice == '0':
            print("感谢使用，再见！")
            break
        else:
            print("[警告] 无效输入，请输入 0-8 之间的数字。")

if __name__ == "__main__":
    main()
