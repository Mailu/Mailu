import git
import tempfile
import argparse
import os
import shutil
import re


VERSION_BRANCH = re.compile("(master|\d+\.\d+)")


def main(upstream, dest):
    shutil.rmtree(dest, ignore_errors=True)
    os.makedirs(dest, exist_ok=True)
    with tempfile.TemporaryDirectory() as clone_path:
        repo = git.Repo.clone_from(upstream, clone_path)
        for branch in repo.refs:
            if not branch.name.startswith("origin/"):
                continue
            name = branch.name[len("origin/"):]
            if not VERSION_BRANCH.match(name):
                continue
            branch.checkout()
            config_path = os.path.join(clone_path, "config")
            if os.path.exists(config_path):
                shutil.copytree(config_path, os.path.join(dest, name))
                print("Imported branch {}".format(name))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("upstream", help="Path to Mailu git repository")
    parser.add_argument("dest", help="Destination directory for data files")
    args = parser.parse_args()
    main(**vars(args))
