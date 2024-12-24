#!/usr/bin/env python3
import argparse
import configparser
import hashlib
import os
import re
import sys
import zlib
from collections import OrderedDict


def locate_git_path(repository, *subpaths):
    """Compute a path inside the repository's .git directory."""
    return os.path.join(repository.git_directory, *subpaths)


def ensure_git_directory(repository, *subpaths, create=False):
    """
    Similar to locate_git_path, but also creates the directory if requested.
    """
    potential_path = locate_git_path(repository, *subpaths)
    if os.path.exists(potential_path):
        if os.path.isdir(potential_path):
            return potential_path
        raise Exception("Path is not a directory: {}".format(potential_path))
    if create:
        os.makedirs(potential_path)
    return potential_path


def ensure_git_file(repository, *subpaths, create=False):
    """
    Similar to locate_git_path, but creates the containing directory if needed.
    """
    if ensure_git_directory(repository, *subpaths[:-1], create=create):
        return locate_git_path(repository, *subpaths)


class SimpleRepository:
    """A minimalist representation of a Git-like repository."""

    def __init__(self, root_path, force=False):
        self.workspace = root_path
        self.git_directory = os.path.join(root_path, ".git")

        if not (force or os.path.isdir(self.git_directory)):
            raise Exception("Not a valid Git repository at {}".format(root_path))

        # Load config file
        self.config_parser = configparser.ConfigParser()
        config_location = ensure_git_file(self, "config")
        if config_location and os.path.exists(config_location):
            self.config_parser.read([config_location])
        elif not force:
            raise Exception("Missing configuration file in .git/config")

        if not force:
            repo_format_version = int(self.config_parser.get("core", "repositoryformatversion"))
            if repo_format_version != 0:
                raise Exception("Unsupported repository format version: {}".format(repo_format_version))


def create_repo(target_path):
    """
    Initialize a new repository in the specified directory.
    """
    new_repo = SimpleRepository(target_path, force=True)

    if os.path.exists(new_repo.workspace):
        if not os.path.isdir(new_repo.workspace):
            raise Exception("{} is not a folder!".format(new_repo.workspace))
        if os.listdir(new_repo.workspace):
            raise Exception("{} is not empty!".format(new_repo.workspace))
    else:
        os.makedirs(new_repo.workspace)

    # Create .git structure
    os.makedirs(new_repo.git_directory)
    ensure_git_directory(new_repo, "branches", create=True)
    ensure_git_directory(new_repo, "objects", create=True)
    ensure_git_directory(new_repo, "refs", "tags", create=True)
    ensure_git_directory(new_repo, "refs", "heads", create=True)

    # Write initial description
    with open(ensure_git_file(new_repo, "description"), "w") as desc_file:
        desc_file.write("Unnamed repository; edit this file 'description' to name the repository.\n")

    # Write initial HEAD
    with open(ensure_git_file(new_repo, "HEAD"), "w") as head_file:
        head_file.write("ref: refs/heads/master\n")

    # Write config
    with open(ensure_git_file(new_repo, "config"), "w") as conf_file:
        conf_file.write(default_repo_config())

    return new_repo


def default_repo_config():
    """
    Return a default configuration block for a newly created repository.
    """
    return (
        "[core]\n"
        "\trepositoryformatversion = 0\n"
        "\tfilemode = false\n"
        "\tbare = false\n"
    )


def locate_existing_repo(starting_path=".", required=True):
    """
    Ascend from starting_path until a .git folder is located.
    """
    search_path = os.path.realpath(starting_path)

    if os.path.isdir(os.path.join(search_path, ".git")):
        return SimpleRepository(search_path)

    # Move to the parent directory
    parent_path = os.path.realpath(os.path.join(search_path, ".."))

    if parent_path == search_path:
        # We have reached the top
        if required:
            raise Exception("No .git directory found in any ancestor.")
        return None

    return locate_existing_repo(parent_path, required)


def present_object(repository, object_name, expected_type=None):
    """
    Print the contents of an object to stdout.
    """
    git_obj = read_object(repository, find_object(repository, object_name, fmt=expected_type))
    sys.stdout.buffer.write(git_obj.serialize())


def read_object(repository, sha_identifier):
    """
    Decompress and parse an object from the repository by its SHA.
    """
    object_path = ensure_git_file(repository, "objects", sha_identifier[:2], sha_identifier[2:])
    with open(object_path, "rb") as obj_stream:
        decompressed = zlib.decompress(obj_stream.read())

    # Format: "type size\0content"
    header_end = decompressed.find(b' ')
    obj_type = decompressed[:header_end]

    size_null = decompressed.find(b'\x00', header_end)
    obj_size = int(decompressed[header_end + 1:size_null])

    if obj_size != len(decompressed) - (size_null + 1):
        raise Exception("Corrupted object {}: bad length".format(sha_identifier))

    raw_content = decompressed[size_null + 1:]

    if obj_type == b'commit':
        return CommitObject(raw_content)
    elif obj_type == b'tree':
        return TreeObject(raw_content)
    elif obj_type == b'tag':
        return TagObject(raw_content)
    elif obj_type == b'blob':
        return BlobObject(raw_content)
    else:
        raise Exception("Unknown object type {} for {}".format(obj_type.decode("ascii"), sha_identifier))


def find_object(repository, name, fmt=None, follow=True):
    """
    Locate an object by partial or full SHA-1 hash.
    """
    if not re.search(r"^[0-9A-Fa-f]{4,40}$", name):
        raise Exception("Invalid object name: {}".format(name))

    name = name.lower()
    if len(name) == 40:
        return name

    # Partial SHA
    potential_dir = ensure_git_directory(repository, "objects", name[:2], create=False)
    if not potential_dir:
        return None

    remainder = name[2:]
    for candidate in os.listdir(potential_dir):
        if candidate.startswith(remainder):
            return name[:2] + candidate

    return None


def write_object(git_object, repository):
    """
    Serialize and write a GitObject, returning its computed SHA-1.
    """
    content = git_object.serialize()
    # Prepare header
    header = git_object.obj_type + b' ' + str(len(content)).encode() + b'\x00' + content
    sha_value = hashlib.sha1(header).hexdigest()

    out_path = ensure_git_file(repository, "objects", sha_value[:2], sha_value[2:], create=True)
    with open(out_path, "wb") as output_stream:
        output_stream.write(zlib.compress(header))

    return sha_value


class GitObject:
    """
    Abstract base for different Git object types.
    """

    def __init__(self, raw_data=None):
        if raw_data is not None:
            self.deserialize(raw_data)

    def serialize(self):
        raise NotImplementedError("Must be overridden in subclass.")

    def deserialize(self, data):
        raise NotImplementedError("Must be overridden in subclass.")


class BlobObject(GitObject):
    obj_type = b'blob'

    def serialize(self):
        return self.content_data

    def deserialize(self, data):
        self.content_data = data


class CommitObject(GitObject):
    obj_type = b'commit'

    def deserialize(self, data):
        self.parsed_kvlm = parse_kvlm(data)

    def serialize(self):
        return serialize_kvlm(self.parsed_kvlm)


class TreeObject(GitObject):
    obj_type = b'tree'

    def deserialize(self, data):
        self.tree_entries = []
        idx = 0
        while idx < len(data):
            space_idx = data.find(b' ', idx)
            mode_str = data[idx:space_idx]
            idx = space_idx + 1
            null_idx = data.find(b'\x00', idx)
            filename = data[idx:null_idx]
            idx = null_idx + 1
            raw_sha = data[idx:idx + 20]
            idx += 20
            self.tree_entries.append(
                (mode_str.decode("ascii"), filename, raw_sha.hex())
            )

    def serialize(self):
        result = b''
        for mode, fname, sha_hex in self.tree_entries:
            result += mode.encode("ascii") + b' ' + fname + b'\x00'
            result += bytes.fromhex(sha_hex)
        return result


class TagObject(CommitObject):
    obj_type = b'tag'


def parse_kvlm(raw_block, start_idx=0, kv_map=None):
    """
    Parse a simple key-value message (like in commits/tags).
    """
    if kv_map is None:
        kv_map = OrderedDict()

    space_pos = raw_block.find(b' ', start_idx)
    newline_pos = raw_block.find(b'\n', start_idx)

    # Base case: if no more headers
    if space_pos < 0 or newline_pos < space_pos:
        kv_map[b''] = raw_block[start_idx + 1:]
        return kv_map

    key = raw_block[start_idx:space_pos]

    line_ender = start_idx
    while True:
        line_ender = raw_block.find(b'\n', line_ender + 1)
        if raw_block[line_ender + 1] != ord(' '):
            break

    value = raw_block[space_pos + 1:line_ender].replace(b'\n ', b'\n')

    if key in kv_map:
        if isinstance(kv_map[key], list):
            kv_map[key].append(value)
        else:
            kv_map[key] = [kv_map[key], value]
    else:
        kv_map[key] = value

    return parse_kvlm(raw_block, start_idx=line_ender + 1, kv_map=kv_map)


def serialize_kvlm(kv_map):
    """
    Convert a key-value list message (kvlm) to bytes.
    """
    result = b''
    for key in kv_map.keys():
        if key == b'':
            continue
        val_list = kv_map[key] if isinstance(kv_map[key], list) else [kv_map[key]]
        for val in val_list:
            result += key + b' ' + val.replace(b'\n', b'\n ') + b'\n'
    result += b'\n' + kv_map[b'']
    return result


def command_init(args):
    create_repo(args.path)


def command_cat_file(args):
    repo = locate_existing_repo()
    present_object(repo, args.object, expected_type=args.type)


def command_hash_object(args):
    repo = locate_existing_repo() if args.write else None

    with open(args.path, "rb") as file_data:
        content = file_data.read()

    if args.type != "blob":
        raise Exception("Unsupported type {} for hashing!".format(args.type))

    candidate_obj = BlobObject(content)
    if repo:
        sha = write_object(candidate_obj, repo)
    else:
        # If not writing, just compute the hash
        header = candidate_obj.obj_type + b' ' + str(len(content)).encode() + b'\x00' + content
        sha = hashlib.sha1(header).hexdigest()
    print(sha)


def command_log(args):
    repo = locate_existing_repo()
    print("digraph commitlog {")
    print("  rankdir=LR;")
    visited_commits = set()
    to_visit = [find_object(repo, args.commit)]

    while to_visit:
        sha = to_visit.pop()
        if sha in visited_commits:
            continue
        visited_commits.add(sha)

        commit = read_object(repo, sha)
        print("  c_{0} [shape=rectangle, label=\"{0}\"];".format(sha))

        if b'parent' not in commit.parsed_kvlm:
            continue

        parent_val = commit.parsed_kvlm[b'parent']
        if not isinstance(parent_val, list):
            parent_val = [parent_val]

        for parent_sha in parent_val:
            parent_sha_str = parent_sha.decode("ascii")
            print("  c_{0} -> c_{1};".format(sha, parent_sha_str))
            to_visit.append(parent_sha_str)
    print("}")


def command_ls_tree(args):
    repo = locate_existing_repo()
    tree_obj = read_object(repo, find_object(repo, args.object))
    for mode, path_bytes, sha_val in tree_obj.tree_entries:
        obj_type = "tree" if mode == "40000" else "blob"
        print("{} {} {}\t{}".format(mode, obj_type, sha_val, path_bytes.decode("ascii")))


def command_checkout(args):
    repo = locate_existing_repo()
    commit_sha = find_object(repo, args.commit)
    if not commit_sha:
        raise Exception("Unknown commit/reference: {}".format(args.commit))

    commit_obj = read_object(repo, commit_sha)
    tree_sha = commit_obj.parsed_kvlm[b'tree'].decode("ascii")

    # Update HEAD
    with open(ensure_git_file(repo, "HEAD"), "w") as head_file:
        head_file.write(commit_sha)

    # Clear the workspace (minus the .git directory)
    for root, dirs, files in os.walk(repo.workspace):
        if root.startswith(repo.git_directory):
            continue
        for f in files:
            os.remove(os.path.join(root, f))
        for d in dirs:
            os.rmdir(os.path.join(root, d))

    # Write out the tree
    tree_obj = read_object(repo, tree_sha)
    recursive_checkout(repo, tree_obj, repo.workspace)


def recursive_checkout(repo, tree_obj, dest_path):
    for mode, fname_bytes, sha_val in tree_obj.tree_entries:
        target_path = os.path.join(dest_path, fname_bytes.decode("ascii"))
        if mode == "40000":
            os.mkdir(target_path)
            subtree = read_object(repo, sha_val)
            recursive_checkout(repo, subtree, target_path)
        else:
            with open(target_path, "wb") as out_file:
                blob_data = read_object(repo, sha_val).serialize()
                out_file.write(blob_data)


def command_commit(args):
    repo = locate_existing_repo()

    # Identify parent commit (HEAD)
    head_sha = find_object(repo, "HEAD")
    if head_sha:
        parent_commit = read_object(repo, head_sha)
        parent_tree = parent_commit.parsed_kvlm[b'tree']
    else:
        parent_commit = None
        parent_tree = None

    # Generate new tree from workspace
    new_tree_sha = build_tree_object(repo, repo.workspace)

    # Create commit object
    new_commit = CommitObject()
    new_commit.parsed_kvlm = OrderedDict()
    new_commit.parsed_kvlm[b'tree'] = new_tree_sha.encode()
    if parent_commit:
        new_commit.parsed_kvlm[b'parent'] = head_sha.encode()
    new_commit.parsed_kvlm[b'author'] = args.author.encode()
    new_commit.parsed_kvlm[b'committer'] = args.author.encode()
    new_commit.parsed_kvlm[b''] = args.message.encode()

    final_sha = write_object(new_commit, repo)

    # Update HEAD
    with open(ensure_git_file(repo, "HEAD"), "w") as head_file:
        head_file.write(final_sha + "\n")

    print("Committed to HEAD: {}".format(final_sha))


def build_tree_object(repo, base_dir):
    """
    Recursively scan the directory and assemble a tree object,
    returning its SHA-1.
    """
    tree_items = []
    for root_path, dirs, files in os.walk(base_dir):
        # Avoid .git
        if ".git" in dirs:
            dirs.remove(".git")
        dirs.sort()
        files.sort()
        relative_root = os.path.relpath(root_path, base_dir)
        for f in files:
            file_rel_path = os.path.join(relative_root, f)
            with open(os.path.join(root_path, f), "rb") as blob_file:
                blob_obj = BlobObject(blob_file.read())
            blob_sha = write_object(blob_obj, repo)
            tree_items.append(("100644", file_rel_path, blob_sha))

        # Recurse into subdirectories
        for d in dirs:
            subtree_rel_path = os.path.join(relative_root, d)
            subtree_sha = build_tree_object(repo, os.path.join(root_path, d))
            tree_items.append(("40000", subtree_rel_path, subtree_sha))

        # Only process the top-level of this call's directory
        break

    tree_obj = TreeObject()
    tree_obj.tree_entries = []
    for mode, rel_path, sha_hex in tree_items:
        tree_obj.tree_entries.append((mode, rel_path.encode("ascii"), sha_hex))
    return write_object(tree_obj, repo)


def command_tag(args):
    repo = locate_existing_repo()
    target_sha = find_object(repo, args.object)
    if not target_sha:
        raise Exception("Cannot locate object: {}".format(args.object))

    new_tag = TagObject()
    new_tag.parsed_kvlm = OrderedDict()
    new_tag.parsed_kvlm[b'object'] = target_sha.encode("ascii")
    new_tag.parsed_kvlm[b'type'] = b'commit'
    new_tag.parsed_kvlm[b'tag'] = args.tagname.encode("ascii")
    new_tag.parsed_kvlm[b'tagger'] = args.author.encode("ascii")
    new_tag.parsed_kvlm[b''] = args.message.encode("ascii")

    tag_sha = write_object(new_tag, repo)
    tag_path = ensure_git_file(repo, "refs", "tags", args.tagname)
    with open(tag_path, "w") as tag_file:
        tag_file.write(tag_sha + "\n")

    print("Created tag '{}' -> {}".format(args.tagname, tag_sha))


def command_rev_parse(args):
    repo = locate_existing_repo()
    print(find_object(repo, args.rev))


def main(argv=sys.argv[1:]):
    parser = argparse.ArgumentParser(description="A simplified Git-like content tracker.")
    subcommands = parser.add_subparsers(title="Available commands", dest="command")
    subcommands.required = True

    # init
    init_cmd = subcommands.add_parser("init", help="Initialize a new repository.")
    init_cmd.add_argument("path", metavar="directory", nargs="?", default=".", help="Target repository directory.")
    init_cmd.set_defaults(func=command_init)

    # cat-file
    catfile_cmd = subcommands.add_parser("cat-file", help="Show the contents of a Git object.")
    catfile_cmd.add_argument("type", metavar="type", choices=["blob", "commit", "tag", "tree"], help="Object type.")
    catfile_cmd.add_argument("object", help="Object to display.")
    catfile_cmd.set_defaults(func=command_cat_file)

    # hash-object
    hashobj_cmd = subcommands.add_parser("hash-object", help="Compute and optionally store the object’s SHA-1.")
    hashobj_cmd.add_argument("-t", "--type", choices=["blob"], default="blob", help="Specify the type of object.")
    hashobj_cmd.add_argument("-w", "--write", action="store_true", help="Store the object in the repository.")
    hashobj_cmd.add_argument("path", help="File to be hashed.")
    hashobj_cmd.set_defaults(func=command_hash_object)

    # log
    log_cmd = subcommands.add_parser("log", help="Display the history leading up to a commit.")
    log_cmd.add_argument("commit", default="HEAD", nargs="?", help="Commit to traverse from.")
    log_cmd.set_defaults(func=command_log)

    # ls-tree
    lstree_cmd = subcommands.add_parser("ls-tree", help="List the contents of a tree object.")
    lstree_cmd.add_argument("object", help="Tree object to display.")
    lstree_cmd.set_defaults(func=command_ls_tree)

    # checkout
    checkout_cmd = subcommands.add_parser("checkout", help="Check out a commit into the working directory.")
    checkout_cmd.add_argument("commit", help="Commit (or branch) to check out.")
    checkout_cmd.set_defaults(func=command_checkout)

    # commit
    commit_cmd = subcommands.add_parser("commit", help="Commit current workspace to the repository.")
    commit_cmd.add_argument("-m", "--message", required=True, help="Commit message.")
    commit_cmd.add_argument("--author", default="Example <example@example.com>", help="Author name and email.")
    commit_cmd.set_defaults(func=command_commit)

    # tag
    tag_cmd = subcommands.add_parser("tag", help="Create a new tag object.")
    tag_cmd.add_argument("tagname", help="Name of the new tag.")
    tag_cmd.add_argument("object", nargs="?", default="HEAD", help="Object the tag should point to.")
    tag_cmd.add_argument("-m", "--message", default="", help="Tag message.")
    tag_cmd.add_argument("--author", default="Example <example@example.com>", help="Tagger name and email.")
    tag_cmd.set_defaults(func=command_tag)

    # rev-parse
    revparse_cmd = subcommands.add_parser("rev-parse", help="Resolve a revision to a full SHA-1.")
    revparse_cmd.add_argument("rev", help="The revision name/commit-ish.")
    revparse_cmd.set_defaults(func=command_rev_parse)

    parsed_args = parser.parse_args(argv)
    parsed_args.func(parsed_args)


if __name__ == "__main__":
    main()
