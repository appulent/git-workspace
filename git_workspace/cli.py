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
def init(config: str, target_dir: str):
    """Initialize workspace by cloning repositories from configuration file."""
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
        # Filter out workspace-config.json files
        other_files = [f for f in existing_files if f.name != 'workspace-config.json']
        if other_files:
            click.echo(f"❌ Target directory '{target_path}' contains files other than workspace-config.json:")
            for file in other_files:
                click.echo(f"   - {file.name}")
            click.echo("The init command requires a directory with only workspace-config.json to avoid conflicts.")
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


@main.command()
def hello():
    """Display a hello world message."""
    click.echo("Hello, World! Welcome to git-workspace CLI tool.")


@main.command()
@click.option('--config-repo', '-r', help='Git repository URL containing workspace configurations')
@click.option('--config-path', '-p', default='workspace-config.json', help='Path to config file within the repo')
def sync(config_repo: str, config_path: str):
    """Sync workspace configuration from a git repository."""
    if not config_repo:
        click.echo("❌ Please provide a config repository URL with --config-repo")
        click.echo("Example: git-workspace sync --config-repo https://github.com/user/my-configs.git")
        sys.exit(1)
    
    import tempfile
    import shutil
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        click.echo(f"📥 Cloning config repository...")
        
        try:
            result = subprocess.run(
                ['git', 'clone', config_repo, str(temp_path / 'config-repo')],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                click.echo(f"❌ Failed to clone config repository: {result.stderr}")
                sys.exit(1)
                
            config_source = temp_path / 'config-repo' / config_path
            config_dest = Path.cwd() / 'workspace-config.json'
            
            if not config_source.exists():
                click.echo(f"❌ Configuration file '{config_path}' not found in repository")
                sys.exit(1)
                
            shutil.copy2(config_source, config_dest)
            click.echo(f"✅ Configuration synced to {config_dest}")
            
            # Ask if user wants to run init
            if click.confirm("🚀 Initialize workspace with the synced configuration?"):
                # Import the init command functionality
                ctx = click.get_current_context()
                ctx.invoke(init, config='workspace-config.json', target_dir='.')
                
        except subprocess.TimeoutExpired:
            click.echo("❌ Timeout while cloning config repository")
            sys.exit(1)
        except Exception as e:
            click.echo(f"❌ Error syncing configuration: {e}")
            sys.exit(1)


if __name__ == '__main__':
    main()