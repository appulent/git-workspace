# Git Workspace CLI Tool

A Python command-line tool for managing multiple git repositories in a workspace.

## Features

- 🚀 Initialize workspace by cloning multiple repositories from a configuration file
- � Fetch updates for all configured repositories with a single command
- �📁 Custom directory names to avoid conflicts
- 🔄 Recursive processing of multiple nested workspaces
- 🛡️ Safe operation - validates configuration and directory state
- 📊 Detailed progress reporting and summary
- ⚡ Continues operation even if some repositories fail to clone

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

# Recursively process all workspace-config.json files in subdirectories
git-workspace init --recursive
```

### Fetch Updates
```bash
# Fetch updates for all repositories in current workspace
git-workspace fetch

# Use custom config file
git-workspace fetch --config my-repos.json

# Use custom target directory
git-workspace fetch --target-dir ./my-workspace

# Recursively fetch updates for all workspaces in subdirectories
git-workspace fetch --recursive
```

### Recursive Workspace Management
Process multiple nested workspaces with a single command:

```bash
# Directory structure:
# my-projects/
# ├── frontend/workspace-config.json
# ├── backend/workspace-config.json  
# └── tools/workspace-config.json

# Initialize all nested workspaces at once
cd my-projects
git-workspace init --recursive

# Fetch updates for all nested workspaces
git-workspace fetch --recursive
```

The recursive mode will:
- 🔍 Find all `workspace-config.json` files in subdirectories
- 📋 Show a preview and ask for confirmation
- 🚀 Process each workspace in its own directory (init or fetch)
- 📊 Provide a comprehensive summary of all operations

## Requirements

- Python 3.8 or higher
- Git installed and available in PATH