# GitLab Group Cloner & Updater

[![CI](https://github.com/tutunak/sb-gitlab/actions/workflows/ci.yml/badge.svg)](https://github.com/sb-gitlab/sb-gitlab/actions/workflows/ci.yml)

A command-line Python tool to **clone** or **update** (_pull_) **all** GitLab repositories under one or more groups (including nested subgroups), organizing them into a mirror directory tree that matches each project’s namespace.

---

## Features

- Recursively discovers all projects in specified GitLab group(s) and their subgroups
- Dedupe projects appearing in multiple groups
- Clones each repo into `DEST//`
- If a target folder already exists and is a Git repo, performs a `git pull` instead of recloning
- Supports both HTTPS and SSH clone URLs
- Handles GitLab API pagination transparently

---

## Requirements

- Python 3.6 or newer
- `git` CLI installed and on your PATH
- Python package: `requests`

---

## Installation

1. **Clone or download** this repository (or save the script)
2. (Optional) Create and activate a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install requests
   ```

---

## Usage

```bash
python sbg.py \
  --gitlab-url     \
  --token          \
  --group-ids      [ …] \
  --dest           \
  [--use-ssh]
```

Arguments:

- `--gitlab-url`  
  Base URL of your GitLab instance (e.g. `https://gitlab.com` or `https://gitlab.example.com`)
- `--token`  
  A Personal Access Token with at least the `api` and `read_repository` scopes
- `--group-ids`  
  One or more group identifiers (either numeric IDs or full paths, e.g. `123`, `my-group/subgroup`)
- `--dest`  
  Root directory where repositories will be cloned/pulled (default: current directory `.`)
- `--use-ssh`  
  If set, clones/pulls via SSH (`git@gitlab…`) instead of HTTPS

---

### Examples

Clone or update all projects under group **42** into `./repos` via HTTPS:

```bash
python sbg.py \
  --gitlab-url https://gitlab.com \
  --token    $GITLAB_TOKEN \
  --group-ids 42 \
  --dest     ./repos
```

Clone or update projects from two groups by full path, using SSH:

```bash
python sbg.py \
  --gitlab-url https://gitlab.example.com \
  --token    $GITLAB_TOKEN \
  --group-ids team/backend team/frontend \
  --dest     ~/gitlab-mirror \
  --use-ssh
```

---

## How It Works

1. **Authentication & API Calls**  
   Uses your PAT in the `Private-Token` header to call the GitLab REST API (`/api/v4/groups/:id/projects` and `/api/v4/groups/:id/subgroups`).
2. **Pagination**  
   Fetches up to 100 items per page and loops until no more pages remain.
3. **Recursive Discovery**  
   Maintains a stack of group IDs to visit. For each group it fetches direct projects and subgroups, pushes new subgroups onto the stack, and marks visited groups to prevent cycles.
4. **Deduplication**  
   Projects are keyed by their unique GitLab project ID so that if the same project appears under multiple parent groups (e.g. via subgroup membership), it's only processed once.
5. **Namespace Folder Structure**  
   Each project’s `namespace.full_path` (e.g. `team/backend`) is used to create a matching folder hierarchy under `--dest`. The repository is cloned or updated in `DEST/team/backend/`.
6. **Clone vs. Pull**
   - If `target/.git` exists: runs `git -C target pull`
   - Otherwise: runs `git clone  target`

---

## Logging

The script uses Python's standard `logging` module for all console output. This provides users with more control over verbosity and output destinations (e.g., logging to a file). By default, it logs messages at the `INFO` level and above to standard output.

---

## Script Reference

```text
sbg.py
├── parse_args()       # CLI argument parsing
├── GitLabCloner
│   ├── _get()         # GET with pagination
│   ├── list_projects()
│   ├── list_subgroups()
│   ├── gather_all_projects()
│   └── clone_or_pull()
└── main()             # Coordinates fetching, dedupe, folder setup, clone/pull loop
```

---

## Troubleshooting

- **Authentication errors**  
  – Ensure your token has the correct scopes (`api`, `read_repository`).  
  – Verify you’re using the right `--gitlab-url`.
- **Git command failures**  
  – Check network connectivity to GitLab  
  – Ensure `git` is on your PATH and supports the `-C` option (Git ≥ 1.8.5)

---

## License

This project is released under the MIT License. Feel free to copy, modify, and distribute!
