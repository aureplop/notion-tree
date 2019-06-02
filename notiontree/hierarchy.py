import argparse
import enum
import functools
import logging
import os
import re
import sys
import tempfile
import time
import urllib.parse
from typing import Dict, Iterable, List, Optional

from notion.block import PageBlock  # type:ignore
from notion.client import NotionClient  # type:ignore

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class PageType(enum.Enum):
    ROOT = 1
    NODE = 2
    LEAVE = 3


class Page:
    def __init__(
        self,
        type: PageType,
        parent_filename: str,
        filename: str,
        notion_url: Optional[str] = None,
        notion_page: Optional[PageBlock] = None,
    ):
        self.type = type
        self.parent_filename = parent_filename
        self.filename = filename
        self.notion_url = notion_url
        self.notion_page = notion_page

    @property
    def title(self) -> str:
        if self.is_index:
            return os.path.basename(os.path.dirname(self.filename))
        return os.path.basename(self.filename)

    @property
    def is_index(self) -> bool:
        return self.filename == "index.md" or self.filename.endswith("/index.md")


def file_hierarchy_to_notion(
    root_parent_url: str, path: str, github_wiki_roots: Iterable[str]
) -> None:
    """
    Export a filesystem hierarchy to Notion.

    Steps:
        1. Extract hierarchy of pages compatible with Notion (incl. missing
            index pages).
        2. Create pages on Notion flatly in root page replacing relative links with
            Notion ones.
        3. Move pages according to hierarchy

    """
    hierarchy = build_local_hierarchy(path)

    filename_to_notion = create_notion_hierarchy(
        root_parent_url=root_parent_url, hierarchy=hierarchy
    )

    update_link_notion_hierarchy(
        hierarchy=hierarchy,
        filename_to_notion=filename_to_notion,
        dir=path,
        github_wiki_roots=github_wiki_roots,
    )

    move_pages_notion_hierarchy(
        hierarchy=hierarchy, filename_to_notion=filename_to_notion
    )


def build_local_hierarchy(path: str) -> List[Page]:
    logger.debug("Detecting file in '%s'", path)

    hierarchy: List[Page] = []
    for walk_index, (dirpath, dirnames, filenames) in enumerate(os.walk(path)):
        if ".git" in dirnames:
            dirnames.remove(".git")

        node = os.path.join(dirpath, "index.md")
        # Add node
        if walk_index == 0:
            hierarchy.append(Page(PageType.ROOT, "", node))
        else:
            parent = os.path.join(os.path.dirname(dirpath), "index.md")
            hierarchy.append(Page(PageType.NODE, parent, node))
        # Add leaves of node
        for f in filenames:
            if f != "index.md" and f.endswith(".md"):
                hierarchy.append(Page(PageType.LEAVE, node, os.path.join(dirpath, f)))
    return hierarchy


def create_notion_hierarchy(
    root_parent_url: str, hierarchy: List[Page], flat: bool = True
) -> Dict[str, PageBlock]:
    logger.debug("Creating hierarchy to Notion (flat:%s)", flat)
    time_start = time.monotonic()

    filename_to_notion: Dict[str, PageBlock] = {}
    root_notion_page: Optional[PageBlock] = None
    for page_index, page in enumerate(hierarchy):
        time_page_start = time.monotonic()

        if page.type is PageType.ROOT:
            parent = get_notion_page(root_parent_url)
        elif flat:
            parent = root_notion_page
        else:
            parent = filename_to_notion[page.parent_filename]
        notion_page = create_notion_page(page, parent=parent)

        filename_to_notion[page.filename] = notion_page
        if page.type is PageType.ROOT:
            root_notion_page = notion_page

        logger.debug(
            "Created stub page %s/%s for (filename:%s) in %.1fsec",
            page_index + 1,
            len(hierarchy),
            page.filename,
            time.monotonic() - time_page_start,
        )

    logger.debug(
        "Created stub pages on Notion (root:%s) in %.1fsec",
        root_notion_page.get_browseable_url() if root_notion_page else "",
        time.monotonic() - time_start,
    )

    return filename_to_notion


def _resolve_github_wiki_link(
    original_ref: str, github_wiki_root: str, dir: str
) -> Optional[str]:
    if not github_wiki_root.endswith("/"):
        github_wiki_root = "{}/".format(github_wiki_root)

    if original_ref.startswith(github_wiki_root):
        # DEV: 'unquote' deserializes %-encoded character.
        ref = urllib.parse.unquote(urllib.parse.urlparse(original_ref).path)
        # DEV: Guess local filename.
        wiki_path = urllib.parse.unquote(urllib.parse.urlparse(github_wiki_root).path)
        ref = ref.replace(wiki_path, "")
        ref = "%s.md" % ref
        # DEV: Make it foundable in filename_to_notion mapping.
        ref = os.path.join(dir, ref)
        return ref

    return None


def _resolve_link(
    matchobj,
    page: Page,
    filename_to_notion: Dict[str, PageBlock],
    dir: str,
    github_wiki_roots: Iterable[str],
):
    original_ref = matchobj.group(0)[1:-1]
    if original_ref.startswith("./"):
        # Relative path to 'page.filename'.
        resolved_ref = os.path.normpath(
            os.path.join(os.path.dirname(page.filename), original_ref)
        )
    else:
        ref = None
        for github_wiki_root in github_wiki_roots:
            ref = _resolve_github_wiki_link(original_ref, github_wiki_root, dir)
            if ref is not None:
                break
        if ref is None:
            return "({})".format(original_ref)
        resolved_ref = ref

    try:
        notion_url = filename_to_notion[resolved_ref].get_browseable_url()
    except KeyError:
        notion_url = original_ref

    logger.debug(
        "Resolved '%s' in '%s' to (local:%s notion:%s)",
        original_ref,
        page.filename,
        resolved_ref,
        notion_url,
    )

    return "({})".format(notion_url)


def update_link_notion_hierarchy(
    hierarchy: List[Page],
    filename_to_notion: Dict[str, PageBlock],
    dir: str,
    github_wiki_roots: Iterable[str],
) -> None:
    logger.debug("Exporting hierarchy with Notion URLs")
    time_start = time.monotonic()

    for page_index, page in enumerate(hierarchy):
        time_page_start = time.monotonic()

        if page.type == PageType.ROOT:
            continue

        try:
            with open(page.filename) as f:
                content = f.read()
        except IOError:
            content = ""
        else:
            resolver = functools.partial(
                _resolve_link,
                page=page,
                filename_to_notion=filename_to_notion,
                dir=dir,
                github_wiki_roots=github_wiki_roots,
            )
            content = re.sub(r"\(.+\)", resolver, content)

        with tempfile.NamedTemporaryFile(mode="w+") as tmp_f:
            tmp_f.write(content)
            tmp_f.flush()

            export_notion_page(filename_to_notion[page.filename], page, tmp_f.name)

        logger.debug(
            "Updated page %s/%s with Notion URLs (filename:%s) in %.1fsec",
            page_index,
            len(hierarchy) - 1,
            page.filename,
            time.monotonic() - time_page_start,
        )

    logger.debug(
        "Updated hierarchy with Notion URLs on Notion in %.1fsec",
        time.monotonic() - time_start,
    )


def move_pages_notion_hierarchy(
    hierarchy: List[Page], filename_to_notion: Dict[str, PageBlock]
) -> None:
    logger.debug("Moving pages according to hierarchy")
    time_start = time.monotonic()

    for page_index, page in enumerate(reversed(hierarchy)):
        time_page_start = time.monotonic()

        if page.type == PageType.ROOT:
            continue

        parent_notion_page = filename_to_notion[page.parent_filename]
        notion_page = filename_to_notion[page.filename]
        notion_page.move_to(parent_notion_page, "first-child")

        logger.debug(
            "Moved page %s/%s (filename:%s) to (filename:%s) in %.1fsec",
            page_index + 1,
            len(hierarchy) - 1,
            page.filename,
            page.parent_filename,
            time.monotonic() - time_page_start,
        )

    logger.debug(
        "Updated hierarchy with Notion URLs on Notion in %.1fsec",
        time.monotonic() - time_start,
    )


# Notion Client


def get_notion_client(token: Optional[str] = None) -> NotionClient:
    if token is None:
        token = os.environ.get("NOTION_TOKEN")
    _notion_client = NotionClient(token_v2=token, monitor=False)
    return _notion_client


def get_notion_page(url: str) -> PageBlock:
    return get_notion_client().get_block(url)


def create_notion_page(page: Page, parent: PageBlock) -> PageBlock:
    notion_page = parent.children.add_new(PageBlock, title=page.title)
    return notion_page


def export_notion_page(notion_page: PageBlock, page: Page, filename: str):
    client = get_notion_client()
    try:
        client.import_file(filename, page_id=notion_page.id, timeout=60)
    except IOError:
        with tempfile.NamedTemporaryFile() as f:
            client.import_file(f.name, page_id=notion_page.id, timeout=60)
    notion_page.title = page.title


# CLI


def start_from_cli(args):
    parser = argparse.ArgumentParser(
        description="Export a local hierarchy to Notion pages"
    )
    parser.add_argument(
        "--root-parent-url", type=str, help="target URL of the root on Notion"
    )
    parser.add_argument("--dir", type=str, help="source directory")
    parser.add_argument(
        "--github-wiki-root",
        type=str,
        help=(
            "GitHub wiki URL to resolve links to Notion URLs (ex: "
            "https://github.com/myname/myproject/wiki)"
        ),
    )
    args = parser.parse_args(args[1:])

    file_hierarchy_to_notion(
        root_parent_url=args.root_parent_url,
        path=args.dir,
        github_wiki_roots=args.github_wiki_root.split(","),
    )


if __name__ == "__main__":
    start_from_cli(sys.argv)
