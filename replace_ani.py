import os

target_dir = r"C:\Users\Anirudh\Downloads\files (2)\shakky\shakky"

for root, dirs, files in os.walk(target_dir):
    for filename in files:
        if filename.endswith(".py") or filename.endswith(".html"):
            filepath = os.path.join(root, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            new_content = content.replace("from Ani ", "from shakky ")
            new_content = new_content.replace("from Ani.", "from shakky.")
            new_content = new_content.replace("import Ani\n", "import shakky\n")
            
            # Additional fixes
            new_content = new_content.replace("from Ani.core.userbot import assistants", "assistants = [1, 2, 3, 4, 5]")

            if content != new_content:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(new_content)
                print(f"Updated: {filepath}")

print("Global replace complete.")
