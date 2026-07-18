import inspect
import dhanhq

print("\n🔍 --- DHANHQ LIBRARY DEEP INSPECTION START --- 🔍")

# 1. Check all available classes/functions inside the library
print("📦 Available attributes in dhanhq module:")
print(dir(dhanhq))

# 2. Inspect the main dhanhq class __init__ method to see exact arguments
try:
    print("\n🛠️ Inspecting dhanhq.__init__ signature:")
    print(inspect.signature(dhanhq.dhanhq.__init__))
except Exception as e:
    print(f"Could not inspect dhanhq.__init__: {e}")

# 3. Look for any context or client related classes inside the module
for name, obj in inspect.getmembers(dhanhq):
    if inspect.isclass(obj):
        print(f"\n🏫 Class found: {name}")
        try:
            print(f"   Constructor parameters: {inspect.signature(obj.__init__)}")
        except:
            pass

print("\n🔍 --- INSPECTION END --- 🔍")
exit() # Stop execution here so it doesn't crash on other logic
