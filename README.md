# Git Workspace CLI Tool

A Python command-line tool for managing multiple git repositories in a workspace.

## Features

- 🚀 Initialize workspace by cloning multiple repositories from a configuration file
- 📁 Custom directory names to avoid conflicts
- 🛡️ Safe operation - validates configuration and directory state
- 📊 Detailed progress reporting and summary
- ⚡ Continues operation even if some repositories fail to clone
- 🔄 Sync configurations from git repositories

## Installation

### Using pipx (Recommended)

```bash
pipx install git-workspace
```

### Using pip

```bash
pip install git-workspace
```

## Quick Start

1. Create a `workspace-config.json` file:
```json
{
  "repositories": [
    "https://github.com/user/repo1.git",
    "https://github.com/user/repo2.git"
  ]
}
```

2. Initialize your workspace:
```bash
git-workspace init
```

## Configuration

### Simple Format
```json
{
  "repositories": [
    "https://github.com/user/repo1.git",
    "https://github.com/user/repo2.git"
  ]
}
```

### Custom Directory Names
```json
{
  "repositories": [
    "https://github.com/user/repo1.git",
    {
      "url": "https://github.com/user/repo2.git",
      "directory": "custom-name"
    }
  ]
}
```

## Usage

### Initialize Workspace
```bash
# Run in current directory with workspace-config.json
git-workspace init

# Use custom config file
git-workspace init --config my-repos.json

# Use custom target directory
git-workspace init --target-dir ./my-workspace
```

### Sync Configuration
```bash
# Sync configuration from a git repository
git-workspace sync --config-repo https://github.com/user/my-configs.git

# Use config from subdirectory
git-workspace sync --config-repo https://github.com/user/configs.git --config-path work/workspace-config.json
```

## Synchronizing Configurations

### Dedicated Config Repository
```bash
# Create a repo for your workspace configs
mkdir my-workspace-configs && cd my-workspace-configs
echo '{"repositories": [...]}' > workspace-config.json
git init && git add . && git commit -m "Add config"

# On any machine
git-workspace sync --config-repo https://github.com/user/my-workspace-configs.git
```

### Workspace as Git Repository  
```bash
mkdir my-workspace && cd my-workspace
git init
echo '{"repositories": [...]}' > workspace-config.json

# Ignore cloned repos, keep only config
echo "*/
!workspace-config.json
!.gitignore" > .gitignore

git add . && git commit -m "Workspace config"
```

## Requirements

- Python 3.8 or higher
- Git installed and available in PATH