#!/usr/bin/env python3
import os
import sys
import argparse
import requests
import subprocess
from urllib.parse import urljoin

def parse_args():
    p = argparse.ArgumentParser(
        description="Clone all GitLab repos under a group (including nested subgroups)."
    )
    p.add_argument("--gitlab-url", required=True,
                   help="Base GitLab URL, e.g. https://gitlab.com")
    p.add_argument("--token", required=True,
                   help="Personal Access Token with api/read_repository scope")
    p.add_argument("--group-id", required=True,
                   help="ID or full path of the group to clone")
    p.add_argument("--dest", default=".",
                   help="Destination directory to clone into")
    p.add_argument("--use-ssh", action="store_true",
                   help="Use SSH URLs instead of HTTP URLs")
    return p.parse_args()

class GitLabCloner:
    def __init__(self, base_url, token, use_ssh):
        self.base_url = base_url.rstrip("/") + "/"
        self.session = requests.Session()
        self.session.headers.update({"Private-Token": token})
        self.use_ssh = use_ssh

    def _get(self, path, params=None):
        """Helper to GET a paginated endpoint."""
        url = urljoin(self.base_url, path.lstrip("/"))
        params = params or {}
        params.setdefault("per_page", 100)
        items = []
        page = 1
        while True:
            params["page"] = page
            r = self.session.get(url, params=params)
            r.raise_for_status()
            chunk = r.json()
            if not chunk:
                break
            items.extend(chunk)
            if len(chunk) < params["per_page"]:
                break
            page += 1
        return items

    def list_subgroups(self, group_id):
        """List all direct subgroups for a group."""
        path = f"/api/v4/groups/{group_id}/subgroups"
        return self._get(path)

    def list_projects(self, group_id):
        """List all direct projects in a group."""
        path = f"/api/v4/groups/{group_id}/projects"
        return self._get(path, params={"include_subgroups": False})

    def gather_all_projects(self, group_id):
        """Recursively gather all projects under group_id."""
        projects = []
        stack = [group_id]
        visited = set()

        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)

            # 1) get projects in this group
            projs = self.list_projects(current)
            projects.extend(projs)

            # 2) get subgroups, and push to stack
            subgs = self.list_subgroups(current)
            for sg in subgs:
                stack.append(sg["id"])

        return projects

    def clone_repo(self, repo_url, dest_folder):
        """Clone a single repo if not already present."""
        repo_name = os.path.basename(repo_url.rstrip("/")).replace(".git", "")
        target_path = os.path.join(dest_folder, repo_name)
        if os.path.isdir(target_path):
            print(f"Skipping {repo_name}, directory exists")
            return

        cmd = ["git", "clone", repo_url, target_path]
        print("Cloning:", " ".join(cmd))
        subprocess.check_call(cmd)

def main():
    args = parse_args()
    cloner = GitLabCloner(args.gitlab_url, args.token, args.use_ssh)

    # 1) gather all projects
    print(f"Fetching projects under group {args.group_id} ...")
    all_projects = cloner.gather_all_projects(args.group_id)
    print(f"Found {len(all_projects)} project(s).")

    # 2) prepare destination
    dest = os.path.abspath(args.dest)
    os.makedirs(dest, exist_ok=True)

    # 3) clone each
    for proj in all_projects:
        url = proj["ssh_url_to_repo"] if args.use_ssh else proj["http_url_to_repo"]
        cloner.clone_repo(url, dest)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("\nAborted by user")
    except Exception as e:
        sys.exit(f"Error: {e}")
