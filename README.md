# sb-gitlab

A simple Python tool for backing up GitLab repositories by cloning all projects within a group, including nested subgroups.

## Features

- Clone all repositories under a specified GitLab group
- Recursively includes all nested subgroups
- Supports both HTTP and SSH URLs for cloning
- Skips repositories that have already been cloned
- Preserves the original repository names

## Requirements

- Python 3.6+
- Git command-line tool installed and in your PATH
- GitLab Personal Access Token with `api` and `read_repository` scopes

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/tutunak/sb-gitlab.git
   cd sb-gitlab
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

```bash
./sbg.py --gitlab-url <GITLAB_URL> --token <YOUR_TOKEN> --group-id <GROUP_ID> [--dest <DESTINATION_DIR>] [--use-ssh]
```

### Arguments

- `--gitlab-url`: Base GitLab URL (e.g., https://gitlab.com)
- `--token`: Your GitLab Personal Access Token
- `--group-id`: ID or full path of the group to clone
- `--dest`: Destination directory for cloning (default: current directory)
- `--use-ssh`: Use SSH URLs instead of HTTP URLs for cloning

## Examples

Clone all repositories from a group using HTTP:

```bash
./sbg.py --gitlab-url https://gitlab.com --token glpat-xxxxxxxxxxxx --group-id my-group --dest ./backups
```

Clone using SSH URLs:

```bash
./sbg.py --gitlab-url https://gitlab.com --token glpat-xxxxxxxxxxxx --group-id my-group --dest ./backups --use-ssh
```

## License

This project is open-source software.
