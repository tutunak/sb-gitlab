#!/usr/bin/env python3
import os
import sys
import argparse
import requests
import subprocess
from urllib.parse import urljoin

def parse_args():
    p = argparse.ArgumentParser(
        description="Clone all GitLab repos under one or more groups "
                    "(including nested subgroups) into folders by namespace."
    )
    p.add_argument("--gitlab-url", required=True,
                   help="Base GitLab URL, e.g. https://gitlab.com")
    p.add_argument("--token", required=True,
                   help="Personal Access Token with api/read_repository scope")
    p.add_argument("--group-ids", required=True, nargs="+",
                   help="One or more group IDs or full paths (e.g. 123 my-group/subgroup)")
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
        url = urljoin(self.base_url, path.lstrip("/"))
        params = params or {}
        params.setdefault("per_page", 100)
        items, page = [], 1
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
        return self._get(f"/api/v4/groups/{group_id}/subgroups")

    def list_projects(self, group_id):
        return self._get(f"/api/v4/groups/{group_id}/projects",
                         params={"include_subgroups": False})

    def gather_all_projects(self, group_id):
        """Recursively gather all projects under group_id."""
        projects = []
        stack, seen_groups = [group_id], set()
        while stack:
            grp = stack.pop()
            if grp in seen_groups:
                continue
            seen_groups.add(grp)

            # fetch projects
            try:
                projs = self.list_projects(grp)
            except requests.HTTPError as e:
                print(f"Warning: cannot fetch projects for group '{grp}': {e}")
                continue
            projects.extend(projs)

            # fetch subgroups
            try:
                subs = self.list_subgroups(grp)
            except requests.HTTPError as e:
                print(f"Warning: cannot fetch subgroups for group '{grp}': {e}")
                continue
            for sg in subs:
                stack.append(sg["id"])

        return projects

    def clone_repo(self, repo_url, target_path):
        """Clone a single repo into target_path (parent dir must exist)."""
        print(f"Cloning into {target_path!r} …")
        subprocess.check_call(["git", "clone", repo_url, target_path])

def main():
    args = parse_args()
    cloner = GitLabCloner(args.gitlab_url, args.token, args.use_ssh)

    # 1) collect & dedupe
    all_projects = {}
    for gid in args.group_ids:
        print(f"Fetching projects under group '{gid}' …")
        for proj in cloner.gather_all_projects(gid):
            all_projects[proj["id"]] = proj

    print(f"Total unique projects to clone: {len(all_projects)}")

    # 2) ensure dest root
    dest_root = os.path.abspath(args.dest)
    os.makedirs(dest_root, exist_ok=True)

    # 3) clone each into its namespace folder
    for proj in all_projects.values():
        # project namespace, e.g. "my-group/subgroup"
        ns = proj.get("namespace", {}).get("full_path")
        if not ns:
            # fallback: derive from path_with_namespace minus project slug
            pwn = proj.get("path_with_namespace", "")
            ns = "/".join(pwn.split("/")[:-1]) if "/" in pwn else ""
        # choose URL
        url = proj["ssh_url_to_repo"] if args.use_ssh else proj["http_url_to_repo"]
        # build local path: dest_root / namespace / project_slug
        project_slug = proj["path"]
        parent_dir = os.path.join(dest_root, ns) if ns else dest_root
        os.makedirs(parent_dir, exist_ok=True)
        target = os.path.join(parent_dir, project_slug)

        if os.path.isdir(target):
            print(f"Skipping {proj['path_with_namespace']!r}, target exists.")
            continue

        try:
            cloner.clone_repo(url, target)
        except subprocess.CalledProcessError as e:
            print(f"Error cloning {proj['path_with_namespace']}: {e}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("\nAborted by user")
    except Exception as e:
        sys.exit(f"Fatal error: {e}")
