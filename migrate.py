import os
import yaml

OUTPUT_PATH = os.path.expanduser('~/Documents/Squirrel Archive/')

def process_file(filepath):
    filepath = os.path.normpath(filepath)
    filename = os.path.basename(filepath)

    if not filepath.startswith('/Users/aonsager/Documents/Squirrel Archive/20'):
        return

    if not (filepath.endswith('.txt') or filepath.endswith('.md')):
        return

    with open(filepath, 'r') as file:
        content = file.read()

    if content.startswith('---'):
        frontmatter, _, _ = content.partition('---\n')[2].partition('---\n')
        metadata = yaml.safe_load(frontmatter)

        folder_path = f'{OUTPUT_PATH}/{metadata["domain"]}/'
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
        output_path = os.path.join(folder_path, f"{filename}")

        with open(output_path, 'w') as f:
            f.write(content)

for root, dirs, files in os.walk(OUTPUT_PATH):
    for file in files:
        process_file(os.path.join(root, file))
