import os

def check_encoding(directory):
    for root, dirs, files in os.walk(directory):
        for f in files:
            if f.endswith('.py'):
                path = os.path.join(root, f)
                try:
                    with open(path, 'rb') as file:
                        file.read().decode('utf-8')
                except UnicodeDecodeError as e:
                    print(f"Invalid UTF-8 in {path}: {e}")
                except Exception as e:
                    print(f"Error reading {path}: {e}")

if __name__ == "__main__":
    check_encoding('.')
