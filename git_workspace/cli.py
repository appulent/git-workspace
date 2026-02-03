"""Command line interface for git-workspace tool."""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Dict, Any

try:
    from importlib import resources
except ImportError:
    # Python < 3.9 fallback
    import importlib_resources as resources

import click
import jsonschema
from jsonschema import ValidationError
from git_workspace import __version__


@click.group()
@click.version_option(version=__version__, prog_name='git-workspace')
def main():
    """Git Workspace CLI tool for managing multiple repositories."""
    pass


@main.command()
@click.option('--config', '-c', default='workspace-config.json', 
              help='Path to the JSON configuration file containing repository URLs.')
@click.option('--target-dir', '-t', default='.', 
              help='Target directory to clone repositories into.')
@click.option('--recursive', '-r', is_flag=True,
              help='Recursively find and process all workspace-config.json files in subdirectories.')
def init(config: str, target_dir: str, recursive: bool):
    """Initialize workspace by cloning repositories from configuration file."""
    if recursive:
        _init_recursive(target_dir, config)
    else:
        _init_single(config, target_dir)


@main.command()
@click.option('--config', '-c', default='workspace-config.json', 
              help='Path to the JSON configuration file containing repository URLs.')
@click.option('--target-dir', '-t', default='.', 
              help='Target directory containing repositories to fetch.')
@click.option('--recursive', '-r', is_flag=True,
              help='Recursively find and process all workspace-config.json files in subdirectories.')
def fetch(config: str, target_dir: str, recursive: bool):
    """Fetch updates for all repositories in workspace configuration."""
    if recursive:
        _fetch_recursive(target_dir, config)
    else:
        _fetch_single(config, target_dir)


def _init_recursive(target_dir: str, config_filename: str):
    """Recursively find and process all workspace config files."""
    target_path = Path(target_dir).resolve()
    
    # Find all config files
    config_files = []
    for root, dirs, files in os.walk(target_path):
        if config_filename in files:
            config_path = Path(root) / config_filename
            config_files.append(config_path)
    
    if not config_files:
        click.echo(f"❌ No '{config_filename}' files found in {target_path} or its subdirectories.")
        sys.exit(1)
    
    click.echo(f"🔍 Found {len(config_files)} workspace configurations:")
    for config_file in config_files:
        rel_path = config_file.parent.relative_to(target_path)
        click.echo(f"   - {rel_path or '.'}")
    click.echo()
    
    if not click.confirm(f"Process all {len(config_files)} workspace configurations?"):
        click.echo("Operation cancelled.")
        sys.exit(0)
    
    results = []
    
    for i, config_file in enumerate(config_files, 1):
        workspace_dir = config_file.parent
        rel_path = workspace_dir.relative_to(target_path) or Path('.')
        
        click.echo(f"[{i}/{len(config_files)}] Processing workspace: {rel_path}")
        click.echo("─" * 60)
        
        try:
            _init_single(str(config_file), str(workspace_dir))
            results.append({
                'path': rel_path,
                'status': 'success',
                'message': 'Workspace initialized successfully'
            })
        except SystemExit as e:
            results.append({
                'path': rel_path,
                'status': 'failed',
                'message': f'Initialization failed (exit code: {e.code})'
            })
        except Exception as e:
            results.append({
                'path': rel_path,
                'status': 'failed',
                'message': f'Unexpected error: {str(e)}'
            })
        
        click.echo()
    
    # Print summary
    _print_recursive_summary(results)


def _print_recursive_summary(results: List[Dict[str, Any]]):
    """Print summary of recursive workspace initialization."""
    click.echo("📋 Recursive Initialization Summary:")
    click.echo("=" * 60)
    
    successful = [r for r in results if r['status'] == 'success']
    failed = [r for r in results if r['status'] == 'failed']
    
    click.echo(f"✅ Successfully initialized: {len(successful)}")
    if successful:
        for result in successful:
            click.echo(f"   - {result['path']}")
    
    if failed:
        click.echo(f"❌ Failed to initialize: {len(failed)}")
        for result in failed:
            click.echo(f"   - {result['path']}: {result['message']}")
    
    total = len(results)
    success_rate = len(successful) / total * 100 if total > 0 else 0
    click.echo()
    click.echo(f"Success rate: {success_rate:.1f}% ({len(successful)}/{total})")


def _init_single(config: str, target_dir: str):
    """Initialize a single workspace (extracted from original init function)."""
    target_path = Path(target_dir).resolve()
    
    # If config is just the filename, look for it in the target directory
    if config == 'workspace-config.json' and not Path(config).exists():
        config_path = target_path / config
    else:
        config_path = Path(config)
    
    # Check if config file exists
    if not config_path.exists():
        click.echo(f"❌ Configuration file '{config_path}' not found.")
        click.echo(f"Create a JSON file with repository URLs. Example:")
        click.echo('{')
        click.echo('  "repositories": [')
        click.echo('    "https://github.com/user/repo1.git",')
        click.echo('    {')
        click.echo('      "url": "https://github.com/user/repo2.git",')
        click.echo('      "directory": "custom-name"')
        click.echo('    }')
        click.echo('  ]')
        click.echo('}')
        sys.exit(1)
    
    # Check if target directory exists and contains files other than workspace-config.json
    if target_path.exists():
        existing_files = list(target_path.iterdir())
        # Filter out allowed files: workspace-config.json, .gitignore, README.md
        allowed_files = {'workspace-config.json', '.gitignore', 'README.md'}
        other_files = [f for f in existing_files if f.name not in allowed_files]
        if other_files:
            click.echo(f"❌ Target directory '{target_path}' contains files other than allowed workspace files:")
            for file in other_files:
                click.echo(f"   - {file.name}")
            click.echo("The init command requires a directory with only workspace configuration files to avoid conflicts.")
            sys.exit(1)
    
    # Create target directory if it doesn't exist
    target_path.mkdir(parents=True, exist_ok=True)
    
    # Load configuration
    try:
        with open(config_path, 'r') as f:
            config_data = json.load(f)
    except json.JSONDecodeError as e:
        click.echo(f"❌ Invalid JSON in configuration file: {e}")
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ Error reading configuration file: {e}")
        sys.exit(1)
    
    # Load and validate against schema
    try:
        # Load schema from package resources
        try:
            with resources.open_text('git_workspace', 'workspace-config.schema.json') as f:
                schema = json.load(f)
        except AttributeError:
            # Python < 3.9 fallback
            with resources.open_text('git_workspace', 'workspace-config.schema.json') as f:
                schema = json.load(f)
        
        jsonschema.validate(config_data, schema)
    except FileNotFoundError:
        click.echo("⚠️  Schema file not found, skipping validation")
    except ValidationError as e:
        click.echo(f"❌ Configuration validation failed:")
        click.echo(f"   {_format_validation_error(e)}")
        click.echo()
        click.echo("💡 Common issues:")
        click.echo("   - Repository URLs must be valid git URLs (ending in .git or GitHub URLs)")
        click.echo("   - Directory names can only contain letters, numbers, hyphens, and underscores")
        click.echo("   - The 'repositories' array cannot be empty")
        click.echo("   - Repository objects must have a 'url' field")
        sys.exit(1)
    except Exception as e:
        click.echo(f"⚠️  Schema validation error: {e}")
        click.echo("Continuing without validation...")
    
    repositories = config_data.get('repositories', [])
    if not repositories:
        click.echo("❌ No repositories found in configuration file.")
        sys.exit(1)
    
    # Create .gitignore file if it doesn't exist
    gitignore_path = target_path / '.gitignore'
    if not gitignore_path.exists():
        gitignore_content = """# Ignore all cloned repositories
*/

# Keep configuration and documentation files
!workspace-config.json
!.gitignore
!README.md
"""
        try:
            with open(gitignore_path, 'w') as f:
                f.write(gitignore_content)
            click.echo(f"📝 Created .gitignore file in {target_path}")
        except Exception as e:
            click.echo(f"⚠️  Could not create .gitignore file: {e}")
    
    click.echo(f"🚀 Initializing workspace with {len(repositories)} repositories...")
    click.echo(f"📁 Target directory: {target_path}")
    click.echo()
    
    results = []
    
    for i, repo_config in enumerate(repositories, 1):
        # Handle both string URLs and objects with URL and directory
        if isinstance(repo_config, str):
            repo_url = repo_config
            repo_name = _get_repo_name_from_url(repo_url)
        elif isinstance(repo_config, dict):
            repo_url = repo_config.get('url')
            if not repo_url:
                click.echo(f"[{i}/{len(repositories)}] ❌ Invalid config: missing 'url' field")
                results.append({
                    'repo_url': str(repo_config),
                    'repo_name': 'unknown',
                    'status': 'failed',
                    'message': "Missing 'url' field in repository configuration"
                })
                continue
            repo_name = repo_config.get('directory') or _get_repo_name_from_url(repo_url)
        else:
            click.echo(f"[{i}/{len(repositories)}] ❌ Invalid config format")
            results.append({
                'repo_url': str(repo_config),
                'repo_name': 'unknown',
                'status': 'failed',
                'message': 'Repository configuration must be a string URL or object with url/directory fields'
            })
            continue
        
        repo_path = target_path / repo_name
        
        # Check if directory already exists
        if repo_path.exists():
            click.echo(f"[{i}/{len(repositories)}] Cloning {repo_name}... ❌ (directory exists)")
            results.append({
                'repo_url': repo_url,
                'repo_name': repo_name,
                'status': 'failed',
                'message': f'Directory {repo_name} already exists'
            })
            continue
        
        click.echo(f"[{i}/{len(repositories)}] Cloning {repo_name}...", nl=False)
        
        try:
            # Clone the repository
            result = subprocess.run(
                ['git', 'clone', repo_url, str(repo_path)],
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode == 0:
                click.echo(" ✅")
                results.append({
                    'repo_url': repo_url,
                    'repo_name': repo_name,
                    'status': 'success',
                    'message': 'Successfully cloned'
                })
            else:
                click.echo(" ❌")
                error_msg = result.stderr.strip() or result.stdout.strip() or 'Unknown error'
                results.append({
                    'repo_url': repo_url,
                    'repo_name': repo_name,
                    'status': 'failed',
                    'message': error_msg
                })
                
        except subprocess.TimeoutExpired:
            click.echo(" ⏰ (timeout)")
            results.append({
                'repo_url': repo_url,
                'repo_name': repo_name,
                'status': 'timeout',
                'message': 'Clone operation timed out after 5 minutes'
            })
        except FileNotFoundError:
            click.echo(" ❌")
            results.append({
                'repo_url': repo_url,
                'repo_name': repo_name,
                'status': 'failed',
                'message': 'Git command not found. Please install Git.'
            })
        except Exception as e:
            click.echo(" ❌")
            results.append({
                'repo_url': repo_url,
                'repo_name': repo_name,
                'status': 'failed',
                'message': f'Unexpected error: {str(e)}'
            })
    
    # Print summary
    _print_summary(results)


def _format_validation_error(error: ValidationError) -> str:
    """Format JSON schema validation error into a user-friendly message."""
    path = " -> ".join(str(p) for p in error.absolute_path) if error.absolute_path else "root"
    
    if error.validator == "required":
        missing_property = error.message.split("'")[1]
        return f"Missing required field '{missing_property}' in repository object at {path}"
    elif error.validator == "type":
        expected_type = error.validator_value
        return f"Expected {expected_type} at {path}, got {type(error.instance).__name__}"
    elif error.validator == "minItems":
        return f"Array at {path} must have at least {error.validator_value} items"
    elif error.validator == "minLength":
        if "directory" in str(error.absolute_path):
            return f"Directory name at {path} cannot be empty"
        else:
            return f"URL at {path} cannot be empty"
    elif error.validator == "pattern":
        if "directory" in str(error.absolute_path):
            return f"Directory name at {path} contains invalid characters (only letters, numbers, hyphens, and underscores allowed): '{error.instance}'"
        else:
            return f"URL at {path} is not a valid git repository URL: '{error.instance}'"
    elif error.validator == "format":
        return f"Invalid URL format at {path}: '{error.instance}'"
    elif error.validator == "additionalProperties":
        return f"Unexpected property at {path}: {error.message}"
    elif error.validator == "oneOf":
        return f"Repository at {path} must be either a string URL or an object with 'url' field"
    else:
        return f"Validation error at {path}: {error.message}"


def _get_repo_name_from_url(url: str) -> str:
    """Extract repository name from git URL."""
    # Handle different URL formats
    if url.endswith('.git'):
        url = url[:-4]
    
    # Extract the last part of the path
    return url.split('/')[-1]


def _print_summary(results: List[Dict[str, Any]]):
    """Print a summary of the cloning operations."""
    click.echo()
    click.echo("📋 Summary:")
    click.echo("=" * 50)
    
    successful = [r for r in results if r['status'] == 'success']
    failed = [r for r in results if r['status'] == 'failed']
    timeouts = [r for r in results if r['status'] == 'timeout']
    
    click.echo(f"✅ Successfully cloned: {len(successful)}")
    if successful:
        for result in successful:
            click.echo(f"   - {result['repo_name']}")
    
    if failed:
        click.echo(f"❌ Failed to clone: {len(failed)}")
        for result in failed:
            click.echo(f"   - {result['repo_name']}: {result['message']}")
    
    if timeouts:
        click.echo(f"⏰ Timed out: {len(timeouts)}")
        for result in timeouts:
            click.echo(f"   - {result['repo_name']}: {result['message']}")
    
    total = len(results)
    success_rate = len(successful) / total * 100 if total > 0 else 0
    click.echo()
    click.echo(f"Success rate: {success_rate:.1f}% ({len(successful)}/{total})")


def _fetch_recursive(target_dir: str, config_filename: str):
    """Recursively find and process all workspace config files for fetching."""
    target_path = Path(target_dir).resolve()
    
    if not target_path.exists():
        click.echo(f"❌ Target directory '{target_path}' does not exist.")
        sys.exit(1)
    
    # Find all workspace config files recursively
    config_files = []
    for root, dirs, files in os.walk(target_path):
        if config_filename in files:
            config_path = Path(root) / config_filename
            config_files.append(config_path)
    
    if not config_files:
        click.echo(f"❌ No '{config_filename}' files found in {target_path} or its subdirectories.")
        sys.exit(1)
    
    click.echo(f"🔍 Found {len(config_files)} workspace configurations:")
    for config_file in config_files:
        rel_path = config_file.parent.relative_to(target_path)
        click.echo(f"   - {rel_path or '.'}")
    click.echo()
    
    if not click.confirm(f"Fetch updates for all {len(config_files)} workspace configurations?"):
        click.echo("Operation cancelled.")
        sys.exit(0)
    
    results = []
    
    for i, config_file in enumerate(config_files, 1):
        workspace_dir = config_file.parent
        rel_path = workspace_dir.relative_to(target_path) or Path('.')
        
        click.echo(f"[{i}/{len(config_files)}] Processing workspace: {rel_path}")
        click.echo("─" * 60)
        
        try:
            _fetch_single(str(config_file), str(workspace_dir))
            results.append({
                'path': rel_path,
                'status': 'success',
                'message': 'Workspace fetched successfully'
            })
        except SystemExit as e:
            results.append({
                'path': rel_path,
                'status': 'failed',
                'message': f'Fetch failed (exit code: {e.code})'
            })
        except Exception as e:
            results.append({
                'path': rel_path,
                'status': 'failed',
                'message': f'Unexpected error: {str(e)}'
            })
        
        click.echo()
    
    # Print summary
    _print_recursive_summary(results)


def _fetch_single(config: str, target_dir: str):
    """Fetch updates for a single workspace."""
    target_path = Path(target_dir).resolve()
    
    # If config is just the filename, look for it in the target directory
    if config == 'workspace-config.json' and not Path(config).exists():
        config_path = target_path / config
    else:
        config_path = Path(config)
    
    # Check if config file exists
    if not config_path.exists():
        click.echo(f"❌ Configuration file '{config_path}' not found.")
        sys.exit(1)
    
    # Check if target directory exists
    if not target_path.exists():
        click.echo(f"❌ Target directory '{target_path}' does not exist.")
        sys.exit(1)
    
    # Load configuration
    try:
        with open(config_path, 'r') as f:
            config_data = json.load(f)
    except json.JSONDecodeError as e:
        click.echo(f"❌ Invalid JSON in configuration file: {e}")
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ Error reading configuration file: {e}")
        sys.exit(1)
    
    repositories = config_data.get('repositories', [])
    if not repositories:
        click.echo("❌ No repositories found in configuration file.")
        sys.exit(1)
    
    click.echo(f"🔄 Fetching updates for {len(repositories)} repositories...")
    click.echo(f"📁 Target directory: {target_path}")
    click.echo()
    
    results = []
    
    for i, repo_config in enumerate(repositories, 1):
        # Handle both string URLs and objects with URL and directory
        if isinstance(repo_config, str):
            repo_url = repo_config
            repo_name = _get_repo_name_from_url(repo_url)
        elif isinstance(repo_config, dict):
            repo_url = repo_config.get('url')
            if not repo_url:
                click.echo(f"[{i}/{len(repositories)}] ❌ Invalid config: missing 'url' field")
                results.append({
                    'repo_url': str(repo_config),
                    'repo_name': 'unknown',
                    'status': 'failed',
                    'message': "Missing 'url' field in repository configuration"
                })
                continue
            repo_name = repo_config.get('directory') or _get_repo_name_from_url(repo_url)
        else:
            click.echo(f"[{i}/{len(repositories)}] ❌ Invalid config format")
            results.append({
                'repo_url': str(repo_config),
                'repo_name': 'unknown',
                'status': 'failed',
                'message': 'Repository configuration must be a string URL or object with url/directory fields'
            })
            continue
        
        repo_path = target_path / repo_name
        
        # Check if directory exists
        if not repo_path.exists():
            click.echo(f"[{i}/{len(repositories)}] Fetching {repo_name}... ❌ (directory not found)")
            results.append({
                'repo_url': repo_url,
                'repo_name': repo_name,
                'status': 'failed',
                'message': f'Directory {repo_name} does not exist. Run init first.'
            })
            continue
        
        # Check if it's a git repository
        if not (repo_path / '.git').exists():
            click.echo(f"[{i}/{len(repositories)}] Fetching {repo_name}... ❌ (not a git repository)")
            results.append({
                'repo_url': repo_url,
                'repo_name': repo_name,
                'status': 'failed',
                'message': f'{repo_name} is not a git repository'
            })
            continue
        
        click.echo(f"[{i}/{len(repositories)}] Fetching {repo_name}...", nl=False)
        
        try:
            # Fetch updates for the repository
            result = subprocess.run(
                ['git', 'fetch', '--all', '--prune'],
                cwd=str(repo_path),
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode == 0:
                click.echo(" ✅")
                results.append({
                    'repo_url': repo_url,
                    'repo_name': repo_name,
                    'status': 'success',
                    'message': 'Successfully fetched'
                })
            else:
                click.echo(" ❌")
                error_msg = result.stderr.strip() or result.stdout.strip() or 'Unknown error'
                results.append({
                    'repo_url': repo_url,
                    'repo_name': repo_name,
                    'status': 'failed',
                    'message': error_msg
                })
                
        except subprocess.TimeoutExpired:
            click.echo(" ⏰ (timeout)")
            results.append({
                'repo_url': repo_url,
                'repo_name': repo_name,
                'status': 'timeout',
                'message': 'Fetch operation timed out after 5 minutes'
            })
        except FileNotFoundError:
            click.echo(" ❌")
            results.append({
                'repo_url': repo_url,
                'repo_name': repo_name,
                'status': 'failed',
                'message': 'Git command not found. Please install Git.'
            })
        except Exception as e:
            click.echo(" ❌")
            results.append({
                'repo_url': repo_url,
                'repo_name': repo_name,
                'status': 'failed',
                'message': f'Unexpected error: {str(e)}'
            })
    
    # Print summary
    _print_fetch_summary(results)


def _print_fetch_summary(results: List[Dict[str, Any]]):
    """Print a summary of the fetch operations."""
    click.echo()
    click.echo("📋 Fetch Summary:")
    click.echo("=" * 50)
    
    successful = [r for r in results if r['status'] == 'success']
    failed = [r for r in results if r['status'] == 'failed']
    timeouts = [r for r in results if r['status'] == 'timeout']
    
    click.echo(f"✅ Successfully fetched: {len(successful)}")
    if successful:
        for result in successful:
            click.echo(f"   - {result['repo_name']}")
    
    if failed:
        click.echo(f"❌ Failed to fetch: {len(failed)}")
        for result in failed:
            click.echo(f"   - {result['repo_name']}: {result['message']}")
    
    if timeouts:
        click.echo(f"⏰ Timed out: {len(timeouts)}")
        for result in timeouts:
            click.echo(f"   - {result['repo_name']}: {result['message']}")
    
    total = len(results)
    success_rate = len(successful) / total * 100 if total > 0 else 0
    click.echo()
    click.echo(f"Success rate: {success_rate:.1f}% ({len(successful)}/{total})")


if __name__ == '__main__':
    main()