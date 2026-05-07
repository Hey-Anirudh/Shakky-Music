import pytgcalls
import inspect

print(f"PyTgCalls version: {getattr(pytgcalls, '__version__', 'unknown')}")
print("Members of pytgcalls:")
for name, obj in inspect.getmembers(pytgcalls):
    if not name.startswith("_"):
        print(f"- {name}")

try:
    from pytgcalls import PyTgCalls
    print("\nMembers of PyTgCalls class:")
    for name, obj in inspect.getmembers(PyTgCalls):
        if not name.startswith("_"):
            print(f"  - {name}")
except Exception as e:
    print(f"Could not inspect PyTgCalls: {e}")
