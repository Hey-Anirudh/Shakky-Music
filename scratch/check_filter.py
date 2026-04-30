from pyrogram import filters
f = filters.user()
print(f"Type: {type(f)}")
print(f"Has add: {hasattr(f, 'add')}")
