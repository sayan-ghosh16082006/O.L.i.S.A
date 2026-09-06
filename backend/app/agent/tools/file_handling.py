from pathlib import Path
import shutil
import time
from langchain.tools import tool


WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent.parent / "project_workspace"


def _safe_path(working_directory: str, relative_path: str) -> Path:
    base = Path(working_directory).resolve()
    rel = Path(relative_path)
    if rel.is_absolute():
        raise ValueError(
            f"'{relative_path}' must be a relative path inside '{base}', not absolute"
        )
    candidate = (base / rel).resolve()
    if not candidate.is_relative_to(base):
        raise ValueError(
            f"Refusing to operate outside working directory: '{relative_path}' "
            f"resolves outside '{base}'"
        )
    return candidate


def _safe_name(name: str) -> None:
    """Reject path separators / traversal in a bare filename component."""
    if "/" in name or "\\" in name or ".." in Path(name).parts:
        raise ValueError(f"Invalid filename component: '{name}'")


@tool("Search file and directories recursively")
async def search_files(working_directory: str, query: str, search_dirs: bool = False) -> list[str]:
    """
    Search recursively for files or directories inside working_directory
    that match a query (partial name or glob pattern).

    Args:
        working_directory: base directory to search
        query: partial name (e.g. 'config') or glob pattern (e.g. '*.py')
        search_dirs: if True, search for directories instead of files

    Returns:
        List of matching paths as strings
    """
    base = Path(working_directory).resolve()
    results = []

    if "*" in query or "?" in query:
        matches = base.rglob(query)
        for p in matches:
            if search_dirs and p.is_dir():
                results.append(str(p))
            elif not search_dirs and p.is_file():
                results.append(str(p))
    else:
        matches = base.rglob("*")
        for p in matches:
            if search_dirs and p.is_dir() and query.lower() in p.name.lower():
                results.append(str(p))
            elif not search_dirs and p.is_file() and query.lower() in p.name.lower():
                results.append(str(p))

    return results


@tool("read file")
async def read_file(working_directory: str, file_path: str) -> str:
    """Reads the content of the file.
    args:
    working_directory : base dir to search
    file_path : the file whose content to be read (relative to working_directory)
    """
    try:
        abs_file_path = _safe_path(working_directory, file_path)
    except ValueError as e:
        return f"Error: {e}"

    if not abs_file_path.is_file():
        return f"Error: {file_path} does not exist"

    try:
        return abs_file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return f"Error: {file_path} is not a UTF-8 text file (binary or unknown encoding)"
    except Exception as e:
        return f"Error reading {file_path}: {e}"


@tool("write file")
async def write_file(title: str, content: str, dirname: str | None = None) -> str:
    """
    Write into a new file (fails if the target already exists — use append_file to update).

    Args:
        title (str): Title of the file (used to build the filename; must not contain path separators).
        content (str): The content to be written into the file.
        suffix (str): The file type/extension (default: "txt").
        dirname (str | None): Subdirectory (relative to the workspace root) to create the file in.

    Returns:
        str: Success or error message.
    """
    try:
        _safe_name(title)
    except ValueError as e:
        return f"Error: {e}"

    workspace_dir = WORKSPACE_ROOT
    try:
        if dirname:
            workspace_dir = _safe_path(str(WORKSPACE_ROOT), dirname)
        workspace_dir.mkdir(parents=True, exist_ok=True)
    except ValueError as e:
        return f"Error: {e}"



    filename = f"{title}"


    output_path = workspace_dir / filename

    if output_path.exists():
        return f"Error: {filename} already exists at {workspace_dir}; use append_file to modify it"

    try:
        output_path.write_text(content, encoding="utf-8")
        return f"Successfully created file {filename} at {workspace_dir}"
    except Exception as e:
        return f"Couldn't write to file {filename}: {e}"


@tool("update file")
async def append_file(working_directory: str, filename: str, content: str) -> str:
    """Append content to an existing file. Fails if the file does not exist.
    args:
    working_directory : the directory where the file exists
    filename : the file to be updated (relative to working_directory)
    content : the content to be appended
    """
    try:
        file_path = _safe_path(working_directory, filename)
    except ValueError as e:
        return f"Error: {e}"

    if not file_path.is_file():
        return f"Error: {filename} does not exist in {working_directory}; use write_file to create it"

    try:
        with file_path.open("a", encoding="utf-8") as f:
            f.write(content + "\n")
        return f"Successfully updated file {filename} at {working_directory}"
    except Exception as e:
        return f"Couldn't update file {filename}: {e}"



@tool("delete files")
async def delete_file(filename: str , dirname: str| None = None, root: str | None = None) -> list[str]:
    """
    Search for directories named dirname under root (or current working directory if root is None),
    then delete the given file inside them.
    Returns a list of deleted file paths.
    """
    root_path = Path(root).resolve() if root else Path.cwd()
    deleted = []
    dirname = dirname if dirname else "project_workspace"

    dirs_to_check = [root_path] + list(root_path.rglob("*"))

    for d in dirs_to_check:
        if d.is_dir() and d.name.lower() == dirname.lower():
            candidate = d / filename
            if candidate.exists() and candidate.is_file():
                candidate.unlink()
                deleted.append(str(candidate.resolve()))

    return deleted if deleted else [f"No file(s) named '{filename}' found in any '{dirname}' directory under {root_path}"]



@tool("copy file")
async def copy_file(source_dir: str, filename: str, target_dir: str) -> str:
    """Copy a file from source to destination.
    args:
    source_dir : the source directory where the original file exists
    filename : the file that needs to be copied (relative to source_dir)
    target_dir : the destination directory where the file will be copied
    """
    if not target_dir:
        return "Please provide a target directory where the file needs to be copied"

    try:
        source_path = _safe_path(source_dir, filename)
    except ValueError as e:
        return f"Error: {e}"

    if not source_path.is_file():
        return f"Error: {filename} does not exist in {source_dir}"

    destination_dir = Path(target_dir).resolve()
    destination_dir.mkdir(parents=True, exist_ok=True)
    try:
        target_file_path = _safe_path(str(destination_dir), filename)
    except ValueError as e:
        return f"Error: {e}"

    try:
        shutil.copy(source_path, target_file_path)
        return f"File {filename} copied successfully to {target_dir}"
    except Exception as e:
        return f"Couldn't copy the file {filename}: {e}"


@tool("move file")
async def move_file(source_dir: str, filename: str, target_dir: str) -> str:
    """Move a file from source to destination.
    args:
    source_dir : the source directory where the original file exists
    filename : the file that needs to be moved (relative to source_dir)
    target_dir : the destination directory where the file will be moved
    """
    if not target_dir:
        return "Please provide a target directory where the file needs to be moved"

    try:
        source_path = _safe_path(source_dir, filename)
    except ValueError as e:
        return f"Error: {e}"

    if not source_path.is_file():
        return f"Error: {filename} does not exist in {source_dir}"

    destination_dir = Path(target_dir).resolve()
    destination_dir.mkdir(parents=True, exist_ok=True)
    try:
        target_file_path = _safe_path(str(destination_dir), filename)
    except ValueError as e:
        return f"Error: {e}"

    if target_file_path.exists():
        return f"Error: {filename} already exists at {target_dir}; refusing to overwrite"

    try:
        shutil.move(str(source_path), str(target_file_path))
        return f"File {filename} moved successfully to {target_dir}"
    except Exception as e:
        return f"Couldn't move the file {filename}: {e}"


@tool("rename file")
async def rename_file(working_directory: str, filename: str, new_name: str) -> str:
    """Rename an existing file (fails rather than silently overwriting a same-named file).
    args:
    working_directory : the directory where the file exists
    filename : the current name of the file (relative to working_directory)
    new_name : the new filename (bare name, no path separators)
    """
    try:
        _safe_name(new_name)
        file_path = _safe_path(working_directory, filename)
    except ValueError as e:
        return f"Error: {e}"

    if not file_path.is_file():
        return f"Error: {filename} does not exist in {working_directory}"

    new_path = file_path.with_name(new_name)
    if new_path.exists():
        return f"Error: {new_name} already exists in {working_directory}; refusing to overwrite"

    try:
        file_path.rename(new_path)
        return f"Renamed {filename} -> {new_name}"
    except Exception as e:
        return f"Couldn't rename {filename} -> {new_name}: {e}"


@tool("create directory")
async def create_directory(working_directory: str, dirname: str) -> str:
    """Create a directory.
    args:
    working_directory : the root directory where the sub dir will be created
    dirname : the directory to be created (relative to working_directory)
    """
    try:
        dir_path = _safe_path(working_directory, dirname)
    except ValueError as e:
        return f"Error: {e}"

    try:
        dir_path.mkdir(parents=True, exist_ok=True)
        return f"Created directory {dir_path}"
    except Exception as e:
        return f"Couldn't create directory {dirname}: {e}"


def _search_directories(working_directory: str, dirname: str) -> list[Path]:
    base = Path(working_directory).resolve()
    return [p for p in base.rglob(dirname) if p.is_dir()]


@tool("delete directory")
async def delete_directory_by_name(working_directory: str, dirname: str, delete_all: bool = False,
                                    match_index: int | None = None) -> str:
    """Deletes a folder found by name under working_directory.

    If multiple directories match `dirname` and neither `delete_all` nor
    `match_index` is given, returns the list of matches instead of deleting
    anything — call again with `match_index` set to the desired entry, or
    `delete_all=True` to remove every match.

    args:
    working_directory : the root directory where the folder exists
    dirname : the folder name (or pattern) to search for and delete
    delete_all : whether to delete every match
    match_index : index into the match list (from a prior ambiguous call) to delete
    """
    matches = _search_directories(working_directory, dirname)
    if not matches:
        return f"Error: directory '{dirname}' not found in {working_directory}"

    if delete_all:
        deleted = []
        for dir_path in matches:
            try:
                shutil.rmtree(dir_path)
                deleted.append(str(dir_path))
            except Exception as e:
                return f"Couldn't delete {dir_path}: {e} (deleted so far: {', '.join(deleted)})"
        return f"Successfully deleted all: {', '.join(deleted)}"

    if len(matches) == 1:
        dir_path = matches[0]
        try:
            shutil.rmtree(dir_path)
            return f"Successfully deleted folder {dir_path}"
        except Exception as e:
            return f"Couldn't delete folder {dir_path}: {e}"

    if match_index is None:
        listing = "\n".join(f"[{i}] {d}" for i, d in enumerate(matches))
        return (
            f"Found {len(matches)} matches for '{dirname}':\n{listing}\n"
            "Call again with match_index set to the one to delete, or delete_all=True."
        )

    if match_index < 0 or match_index >= len(matches):
        return f"Invalid match_index {match_index}. Found {len(matches)} matches."

    dir_path = matches[match_index]
    try:
        shutil.rmtree(dir_path)
        return f"Successfully deleted folder {dir_path}"
    except Exception as e:
        return f"Couldn't delete folder {dir_path}: {e}"


    

