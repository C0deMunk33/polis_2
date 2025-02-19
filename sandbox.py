import os
import sys
import importlib.util
from pathlib import Path

def check_file_exists(filepath):
    return os.path.exists(filepath)

def check_module_importable(module_name):
    try:
        importlib.import_module(module_name)
        return True
    except ImportError as e:
        return str(e)

def should_skip_directory(dirname):
    skip_dirs = {
        '__pycache__',
        '.git',
        '.pytest_cache',
        'venv',
        'env',
        '.env',
        'node_modules',
        '.vscode',
        '.idea'
    }
    return dirname in skip_dirs or dirname.startswith('.')

def main():
    print("\n=== Current Working Directory ===")
    print(os.getcwd())
    
    print("\n=== Project Structure ===")
    for root, dirs, files in os.walk('.'):
        # Remove directories we want to skip
        dirs[:] = [d for d in dirs if not should_skip_directory(d)]
        
        level = root.replace('.', '').count(os.sep)
        indent = ' ' * 4 * level
        
        # Don't print root directory name for top level
        if level > 0:
            print(f"{indent}{os.path.basename(root)}/")
        
        subindent = ' ' * 4 * (level + 1)
        for f in sorted(files):
            if not f.startswith('.') and not f.endswith('.pyc'):
                print(f"{subindent}{f}")
    
    print("\n=== Required Files Check ===")
    required_files = [
        'server.py',
        'index.html',
        'directory.py',
        'common.py',
        'agent.py'
    ]
    
    for file in required_files:
        exists = check_file_exists(file)
        print(f"{file}: {'✓' if exists else '✗'}")
    
    print("\n=== Required Modules Check ===")
    required_modules = [
        'flask',
        'pydantic',
        'sqlite3'
    ]
    
    for module in required_modules:
        importable = check_module_importable(module)
        if importable is True:
            print(f"{module}: ✓")
        else:
            print(f"{module}: ✗ ({importable})")

if __name__ == "__main__":
    main()