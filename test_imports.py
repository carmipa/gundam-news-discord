
import sys
import os
import asyncio

# Adiciona o diretório atual ao path para importar módulos
sys.path.append(os.getcwd())

try:
    print("Testing imports in core.html_monitor...")
    from core.html_monitor import check_official_sites
    print("✅ Import successful!")
except Exception as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)

print("✅ Syntax check passed.")
