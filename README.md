# notion-tree

Hierarchic operations with Notion API, thanks to [notion-py](https://github.com/jamalex/notion-py).

## Requirements

- Python ≥ 3.6
- aureplop/notion-py, fork of https://github.com/jamalex/notion-py, with importFile feature

## Installation

```sh
# Required as PyPI does not accept package with dependency links
$ pip install git+https://github.com/aureplop/notion-py.git@feat-import-file#egg=notion-999
$ pip install notion-tree
```

## Usage

```
# Obtain the `token_v2` value by inspecting your browser cookies on a logged-in session on Notion.so
$ NOTION_TOKEN=...
$ python -m notiontree.hierarchy --dir path/to/local/root --root-parent-url https://www.notion.so/id/to/parent/of/local/root
```

Assuming you had this hierarchy on Notion:
```
workspace
└── parent-root  # URL: https://www.notion.so/id/to/parent/of/local/root
```
And that you have this local structure:
```
path/to/local
└── root
    ├── index.md
    ├── dir1
    │   ├── index.md
    │   └── page1.md
    └── dir2
        └── page2.md
```
After running the command above, you will get this structure on your Notion workspace:
```
workspace
└── parent-root           # URL: https://www.notion.so/id/to/parent/of/local/root
    └── root              # Includes links to dir1 and dir2 + content of root/index.md
        ├── dir1          # Includes links to dir1/page1.md + content of root/dir1/index.md
        │   └── page1.md
        └── dir2          # Includes links to dir2/page2.md
            └── page2.md
```

## Todos

- Split 'notiontree/hierarchy.py' to multiple modules.
- Use 'click' for CLI.
- Document --github-wiki-root in README.
- Create stub pages in another page than 'root' to be able to import root index.html w/o removing other stub pages.
- Accept other filenames for index files (currently limited to 'index.md').
- Improve link resolver configuration.
