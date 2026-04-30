from pyrogram import filters
f = filters.user()
print(f"Has remove: {hasattr(f, 'remove')}")
