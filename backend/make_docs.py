import ast
import os

def parse_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())
    
    file_data = {
        "imports": [],
        "classes": [],
        "functions": []
    }

    for node in tree.body:
        # Собираем импорты (связи)
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.Import):
                for n in node.names:
                    file_data["imports"].append(n.name)
            else:
                file_data["imports"].append(f"from {node.module} import ...")

        # Собираем классы и их методы
        elif isinstance(node, ast.ClassDef):
            methods = []
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    methods.append({
                        "name": item.name,
                        "args": [a.arg for a in item.args.args if a.arg != 'self'],
                        "doc": ast.get_docstring(item) or "Описание отсутствует",
                        "is_async": isinstance(item, ast.AsyncFunctionDef)
                    })
            file_data["classes"].append({
                "name": node.name,
                "doc": ast.get_docstring(node) or "Класс без описания",
                "methods": methods
            })

        # Одиночные функции
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            file_data["functions"].append({
                "name": node.name,
                "args": [a.arg for a in node.args.args],
                "doc": ast.get_docstring(node) or "Описание отсутствует",
                "is_async": isinstance(node, ast.AsyncFunctionDef)
            })
    return file_data

def generate_notion_md(root_dir="."):
    md = "# 🏗 Технический Атлас: MyMovieTrack 2.0\n\n"
    target_dirs = ["services", "handlers", "database", "web_app"]
    
    for folder in target_dirs:
        if not os.path.exists(folder): continue
        md += f"## 📁 Модуль: `{folder.upper()}`\n---\n"
        
        for file in os.listdir(folder):
            if not file.endswith(".py") or file.startswith("__"): continue
            data = parse_file(os.path.join(folder, file))
            
            md += f"### 📄 Файл `{file}`\n"
            md += f"> **Связи:** `{', '.join(data['imports'][:5])}...`\n\n"
            
            if data["classes"]:
                for cls in data["classes"]:
                    md += f"#### 🏛 Класс `{cls['name']}`\n*{cls['doc']}*\n"
                    md += "| Метод | Аргументы | Описание |\n|---|---|---|\n"
                    for m in cls["methods"]:
                        prefix = "⚡ " if m["is_async"] else "⚙️ "
                        md += f"| `{prefix}{m['name']}` | `{m['args']}` | {m['doc']} |\n"
                    md += "\n"

            if data["functions"]:
                md += "#### 🔧 Глобальные функции\n"
                md += "| Функция | Аргументы | Описание |\n|---|---|---|\n"
                for f in data["functions"]:
                    prefix = "⚡ " if f["is_async"] else "⚙️ "
                    md += f"| `{prefix}{f['name']}` | `{f['args']}` | {f['doc']} |\n"
                md += "\n"
    
    with open("NOTION_DUMP.md", "w", encoding="utf-8") as f:
        f.write(md)
    print("✅ Супер-реестр готов! Забирай NOTION_DUMP.md")

if __name__ == "__main__":
    generate_notion_md()