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

def get_directory_structure(directory_path='.'):
    """
    Returns a formatted string representing the directory structure.
    
    Args:
        directory_path (str): Path to the directory to scan. Defaults to current directory.
    
    Returns:
        str: Formatted string showing the directory structure
    """
    output = []
    
    for root, dirs, files in os.walk(directory_path):
        # Remove directories we want to skip
        dirs[:] = [d for d in dirs if not should_skip_directory(d)]
        
        level = root.replace(directory_path, '').count(os.sep)
        indent = ' ' * 4 * level
        
        # Don't print root directory name for top level
        if level > 0:
            output.append(f"{indent}{os.path.basename(root)}/")
        
        subindent = ' ' * 4 * (level + 1)
        for f in sorted(files):
            if not f.startswith('.') and not f.endswith('.pyc'):
                output.append(f"{subindent}{f}")
    if len(output) == 0:
        return "No files found"
    return '\n'.join(output)

def main():
    print(get_directory_structure())

if __name__ == "__main__":
    main()