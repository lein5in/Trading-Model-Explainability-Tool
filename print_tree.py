import os

EXCLUDE_DIRS = {
    ".git", "node_modules", "venv", "__pycache__",
    ".pytest_cache", "dist", "build", ".vite"
}

def print_tree(root=".", prefix=""):
    entries = sorted(os.listdir(root))
    entries = [e for e in entries if e not in EXCLUDE_DIRS]
    for i, entry in enumerate(entries):
        path = os.path.join(root, entry)
        connector = "└── " if i == len(entries) - 1 else "├── "
        print(prefix + connector + entry)
        if os.path.isdir(path):
            extension = "    " if i == len(entries) - 1 else "│   "
            print_tree(path, prefix + extension)

print_tree(".")