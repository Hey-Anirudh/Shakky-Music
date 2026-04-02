import os

target_dir = r"C:\Users\Anirudh\Downloads\files (2)\shakky\shakky"

for root, dirs, files in os.walk(target_dir):
    for filename in files:
        if filename.endswith(".py") or filename.endswith(".html"):
            filepath = os.path.join(root, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            new_content = content.replace('"Ani/', '"shakky/')
            new_content = new_content.replace('"Ani.', '"shakky.')
            new_content = new_content.replace('"Ani"', '"shakky"')
            new_content = new_content.replace("'Ani.", "'shakky.")
            new_content = new_content.replace("'Ani/", "'shakky/")
            new_content = new_content.replace("'Ani'", "'shakky'")

            if content != new_content:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(new_content)
                print(f"Updated: {filepath}")

print("String quote replacements complete.")
