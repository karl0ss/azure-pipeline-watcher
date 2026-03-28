"""
Azure Pipeline Watcher - Monitor Azure DevOps pipelines.
 
This module provides the CLI interface for the pipeline watcher.
"""

import json
import os
import sys
import time
import webbrowser
import requests
import subprocess
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from dateutil.parser import isoparse
from tabulate import tabulate
from azure.identity import DefaultAzureCredential
from . import __version__

# Type aliases for better readability
PipelineData = Dict[str, Any]
PipelineList = List[Dict[str, Any]]


def get_config_dir() -> str:
    """
    Get the user's config directory.

    Returns:
        The path to the configuration directory, which is platform-specific:
        - Windows: %LOCALAPPDATA%\azure-pipeline-watcher
        - Linux/macOS: ~/.config/azure-pipeline-watcher
    """
    home = os.path.expanduser("~")
    if sys.platform == "win32":
        return os.path.join(home, "AppData", "Local", "azure-pipeline-watcher")
    else:
        return os.path.join(home, ".config", "azure-pipeline-watcher")


def get_config_path() -> str:
    """
    Get the path to the configuration file.

    Returns:
        The full path to config.json in the user's config directory.
    """
    return os.path.join(get_config_dir(), "config.json")


def load_config() -> Dict[str, Any]:
    """
    Load configuration from JSON file.

    Returns:
        The configuration dictionary loaded from config.json.

    Raises:
        SystemExit: If the config file is not found or contains invalid JSON.
    """
    config_path = get_config_path()
    try:
        with open(config_path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: Configuration file '{config_path}' not found.")
        print("Please run 'pipeline-watcher init' to create a config file first.")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in configuration file: {e}")
        sys.exit(1)


def save_config(config: Dict[str, Any]) -> None:
    """
    Save configuration to JSON file.

    Args:
        config: The configuration dictionary to save.

    Prints:
        A confirmation message with the path where configuration was saved.
    """
    config_dir = get_config_dir()
    os.makedirs(config_dir, exist_ok=True)
    config_path = get_config_path()
    with open(config_path, "w") as f:
        json.dump(config, f, indent=4)
    print(f"Configuration saved to {config_path}")


def init_config(organization: str | None = None, project: str | None = None) -> None:
    """
    Initialize configuration file interactively or with provided values.

    Args:
        organization: Azure DevOps organization name. If not provided,
            the user will be prompted to enter it interactively.
        project: Azure DevOps project name. If not provided,
            the user will be prompted to enter it interactively.

    The configuration is saved to config.json with the following structure:
    {
        "azure_devops": {
            "organization": str,
            "project": str
        },
        "polling_interval_minutes": int (default: 10)
    }
    """
    config_dir = get_config_dir()
    os.makedirs(config_dir, exist_ok=True)
    config_path = get_config_path()
    
    if organization is None:
        organization = input("Enter your Azure DevOps organization name: ").strip()
    if project is None:
        project = input("Enter your Azure DevOps project name: ").strip()
    
    config = {
        "azure_devops": {
            "organization": organization,
            "project": project,
        },
        "polling_interval_minutes": 10
    }
    
    save_config(config)


def play_notification() -> None:
    """
    Play a notification sound based on the current platform.

    Platform-specific behavior:
        - Windows: Uses winsound.Beep() to play a 800 Hz beep for 300ms
        - macOS: Uses afplay to play the Glass.aiff system sound
        - Linux: Tries paplay/aplay with common notification sound paths,
            falls back to printing a bell character
    """
    try:
        if sys.platform == 'win32':
            # Windows: Use winsound for a simple beep
            import winsound
            # Beep at 800 Hz for 300ms
            winsound.Beep(800, 300)
        elif sys.platform == 'darwin':
            # macOS: Use afplay with a system sound
            subprocess.run(
                ["afplay", "/System/Library/Sounds/Glass.aiff"],
                capture_output=True,
                check=False
            )
        else:
            # Linux: Use paplay or aplay with a sample sound if available
            # Try various common Linux notification sounds
            sound_files = [
                "/usr/share/sounds/notifications/basso.ogg",
                "/usr/share/sounds/gnome-default-alert.ogg",
                "/usr/share/sounds/popcorn.wav",
            ]
            for sound_file in sound_files:
                if os.path.exists(sound_file):
                    try:
                        subprocess.run(
                            ["paplay", sound_file],
                            capture_output=True,
                            check=False
                        )
                        return
                    except FileNotFoundError:
                        try:
                            subprocess.run(
                                ["aplay", sound_file],
                                capture_output=True,
                                check=False
                            )
                            return
                        except FileNotFoundError:
                            continue
            # Fallback: print a bell character
            print('\a', end='')
    except Exception:
        pass  # Silent fail if notification doesn't work


def get_access_token(credential: Any = None) -> str:
    """
    Get access token from Azure using Azure SDK.
    
    Uses the DefaultAzureCredential which supports multiple authentication methods:
    - Azure CLI login (az login)
    - Managed Identity
    - Service Principal with client secret/cert
    - Environment variables
    
    Args:
        credential: Optional existing credential to refresh. If None, creates a new one.
    
    Returns:
        The access token string for Azure DevOps.
    
    Raises:
        SystemExit: If no valid credentials are available.
    
    Note:
        Resource ID 499b84ac-1321-427f-aa17-267ca6975798 is for Azure DevOps.
    """
    try:
        # Use DefaultAzureCredential which automatically uses az CLI login
        if credential is None:
            credential = DefaultAzureCredential()
        token = credential.get_token("499b84ac-1321-427f-aa17-267ca6975798/.default")
        return token.token
    except Exception as e:
        print("Error: Failed to get Azure access token.")
        print("Please run 'az login' to authenticate with Azure.")
        print(f"Details: {e}")
        sys.exit(1)


def get_current_user_info() -> tuple[str, str]:
    """
    Get the email and username of the currently logged-in Azure user.

    Returns:
        A tuple containing (email, username) of the currently logged-in user.

    Raises:
        SystemExit: If the Azure CLI command fails (e.g., not logged in).
    """
    try:
        use_shell = sys.platform == 'win32'
        result = subprocess.run(
            ["az", "account", "show", "--out", "json"],
            capture_output=True,
            text=True,
            check=True,
            shell=use_shell
        )
        account_info = json.loads(result.stdout)
        email = account_info.get("user", {}).get("name", "unknown")
        username = email.split('@')[0] if '@' in email else email
        return (email, username)
    except subprocess.CalledProcessError as e:
        print("Error: Failed to get Azure account information.")
        print(f"Details: {e.stderr}")
        sys.exit(1)


def parse_iso_datetime(value: str) -> datetime | None:
    """
    Parse ISO format datetime string.

    Args:
        value: The ISO format datetime string to parse.

    Returns:
        A datetime object if parsing succeeds, None otherwise.
    """
    if not value:
        return None
    return isoparse(value)


def list_running_pipelines(org_name: str, project: str, access_token: str, user_email: str, user_name: str) -> List[Dict[str, Any]]:
    """
    List all running pipelines in a project for the current user.

    Args:
        org_name: Azure DevOps organization name.
        project: Project name within the organization.
        access_token: Azure DevOps access token for authentication.
        user_email: The email address of the current user.
        user_name: The display name of the current user.

    Returns:
        A list of pipeline dictionaries that are currently running
        and were triggered by the current user.

    Note:
        This function filters pipelines by checking if the user's name
        or email appears in the 'requestedFor' field of the pipeline.
    """
    import urllib.parse
    project_name_encoded = urllib.parse.quote(project)
    builds_url = f"https://dev.azure.com/{org_name}/{project_name_encoded}/_apis/build/builds?api-version=7.1&$expand=definition"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(builds_url, headers=headers)
        if response.status_code != 200:
            print(f"Error: Failed to get builds. Status: {response.status_code}")
            print(f"Response: {response.text}")
            return []
        
        builds_data = response.json()
        builds = builds_data.get('value', [])
        
        # Filter to only running builds for the current user
        running_pipelines = []
        for build in builds:
            state = build.get('state', '')
            status = build.get('status', '')
            is_running = (state in ['inProgress', 'queueing'] or 
                         status in ['inProgress', 'queueing', 'partiallySucceeded'])
            
            # Check if this build was triggered by the current user
            requested_for = build.get('requestedFor', {})
            requested_for_name = requested_for.get('displayName', '') if requested_for else ''
            requested_for_email = requested_for.get('uniqueName', '') if requested_for else ''
            
            if is_running and (user_name.lower() in requested_for_name.lower() or 
                               user_email.lower() in requested_for_email.lower()):
                running_pipelines.append(build)
        
        return running_pipelines
        
    except Exception as e:
        print(f"Error: Failed to fetch builds: {e}")
        return []


def list_finished_pipelines(org_name: str, project: str, access_token: str, user_email: str, user_name: str, minutes: int = 30) -> List[Dict[str, Any]]:
    """
    List all finished pipelines in a project for the current user within the last N minutes.

    Args:
        org_name: Azure DevOps organization name.
        project: Project name within the organization.
        access_token: Azure DevOps access token for authentication.
        user_email: The email address of the current user.
        user_name: The display name of the current user.
        minutes: Number of minutes back to look for finished pipelines (default: 30).

    Returns:
        A list of pipeline dictionaries that have finished within the specified
        time window and were triggered by the current user.

    Note:
        This function filters pipelines by checking if the user's name
        or email appears in the 'requestedFor' field of the pipeline.
    """
    import urllib.parse
    import datetime
    project_name_encoded = urllib.parse.quote(project)
    
    # Calculate cutoff time
    cutoff_time = datetime.datetime.now(timezone.utc) - datetime.timedelta(minutes=minutes)
    
    # Get all builds without status filter (to get all finished states)
    builds_url = f"https://dev.azure.com/{org_name}/{project_name_encoded}/_apis/build/builds?api-version=7.1&$expand=definition"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(builds_url, headers=headers)
        if response.status_code != 200:
            print(f"Error: Failed to get builds. Status: {response.status_code}")
            print(f"Response: {response.text}")
            return []
        
        builds_data = response.json()
        builds = builds_data.get('value', [])
        
        # Filter to only finished builds for the current user within the time window
        finished_pipelines = []
        for build in builds:
            state = build.get('state', '')
            status = build.get('status', '')
            
            # Check if build is in finished state (not inProgress or queueing)
            is_finished = (state == 'completed' or 
                          status in ['completed', 'succeeded', 'failed', 'cancelled', 'partiallySucceeded'])
            
            if not is_finished:
                continue
            
            # Parse finish time
            finish_time = parse_iso_datetime(build.get('finishTime'))
            if not finish_time:
                continue
            
            # Convert to UTC for comparison
            if finish_time.tzinfo is None:
                finish_time = finish_time.replace(tzinfo=timezone.utc)
            
            # Check if within time window
            if finish_time < cutoff_time:
                continue
            
            # Check if this build was triggered by the current user
            requested_for = build.get('requestedFor', {})
            requested_for_name = requested_for.get('displayName', '') if requested_for else ''
            requested_for_email = requested_for.get('uniqueName', '') if requested_for else ''
            
            if (user_name.lower() in requested_for_name.lower() or 
                user_email.lower() in requested_for_email.lower()):
                finished_pipelines.append(build)
        
        return finished_pipelines
        
    except Exception as e:
        print(f"Error: Failed to fetch builds: {e}")
        return []


def format_pipeline_info(run: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract and format key information from a pipeline/build run.

    Args:
        run: A pipeline/build run dictionary from the Azure DevOps API.

    Returns:
        A formatted dictionary containing extracted information including:
        - id: Pipeline ID
        - name: Pipeline name
        - status: Pipeline status
        - queue_time, start_time, finish_time: Parsed datetime objects
        - url, build_url: URLs for the pipeline
        - requested_for: Display name of the user who requested the build
        - duration: String representation of the build duration
        - finish_time_str: Formatted finish time string
    """
    result = {
        "id": run.get('id', 'N/A'),
        "name": run.get('name', 'N/A'),
        "status": run.get('status', 'N/A'),
        "queue_time": None,
        "start_time": None,
        "finish_time": None,
        "url": run.get('url', ''),
        "requested_for": "",
        "build_url": "",
        "finish_time_str": ""
    }
    
    # Get requested for info
    requested_for = run.get('requestedFor', {})
    if requested_for:
        result["requested_for"] = requested_for.get('displayName', '')
    
    # Parse timestamps
    result["queue_time"] = parse_iso_datetime(run.get('queueTime'))
    result["start_time"] = parse_iso_datetime(run.get('startTime'))
    result["finish_time"] = parse_iso_datetime(run.get('finishTime'))
    
    # Get pipeline name from definition
    definition = run.get('definition', {})
    if definition and isinstance(definition, dict):
        result["name"] = definition.get('name', run.get('name', 'N/A'))
    else:
        result["name"] = run.get('name', 'N/A')
    
    # Build URL for hyperlink (use web URL instead of REST API URL)
    if result["url"]:
        # Convert REST API URL to web URL
        # API URL format: https://dev.azure.com/org/project/_apis/build/Builds/209231 (capital B)
        # Web URL format: https://dev.azure.com/org/project/_build/results?buildId=209231
        # Replace _apis/build/Builds with _build/results?buildId=
        result["build_url"] = result["url"].replace("/_apis/build/Builds/", "/_build/results?buildId=")
    
    # Calculate duration
    if result["start_time"] and result["finish_time"]:
        duration = result["finish_time"] - result["start_time"]
        result["duration"] = str(duration).split('.')[0]
        # Format finish time for finished pipelines
        if result["finish_time"]:
            result["finish_time_str"] = result["finish_time"].strftime('%H:%M:%S')
    elif result["start_time"]:
        # Convert start_time to local timezone for duration calculation
        local_time = result["start_time"].astimezone()
        now = datetime.now(timezone.utc).astimezone()
        duration = now - local_time
        result["duration"] = str(duration).split('.')[0]
    else:
        result["duration"] = "N/A"
    
    return result


def display_pipelines_tabular(pipelines: List[Dict[str, Any]], title: str = "Running", print_header: bool = True, polling_interval_minutes: int = 10) -> None:
    """
    Display pipelines in a tabular format.

    Args:
        pipelines: A list of pipeline dictionaries to display.
        title: The title to display above the table (default: "Running").
        print_header: Whether to print the next poll timestamp header (default: True).
        polling_interval_minutes: The polling interval for calculating next poll time (default: 10).

    Note:
        When title is "Finished (Last 10 mins)", the table includes a "Finish Time" column.
        Otherwise, it shows a simplified table with just ID, Name, Status, and Duration.
    """
    if print_header:
        # Print next poll timestamp based on polling interval
        now = datetime.now(timezone.utc).astimezone()
        from datetime import timedelta
        next_poll = now + timedelta(minutes=polling_interval_minutes)
        print(f"Next poll: {next_poll.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"--- {title} Pipelines ---")
    
    if not pipelines:
        print(f"No {title.lower()} pipelines found.\n")
        return
    
    # Prepare data rows with clickable build IDs
    data = []
    for i, run in enumerate(pipelines, 1):
        info = format_pipeline_info(run)
        # Format build ID with hyperlink - click to open in browser
        build_link = f"\033]8;;{info['build_url']}\033\\{info['id']}\033]8;;\033\\"
        if title == "Finished (Last 10 mins)" and info['finish_time_str']:
            data.append([
                str(i),
                build_link,
                info['name'],
                info['status'],
                info['finish_time_str'],
                info['duration']
            ])
        else:
            data.append([
                str(i),
                build_link,
                info['name'],
                info['status'],
                info['duration']
            ])
    
    # Build table using tabulate
    if title == "Finished (Last 30 mins)":
        headers = ["#", "ID", "Name", "Status", "Finish Time", "Duration"]
    else:
        headers = ["#", "ID", "Name", "Status", "Duration"]
    table = tabulate(data, headers=headers, tablefmt="pipe")
    print(f"\n{table}")
    print()


def clear_screen() -> None:
    """
    Clear the terminal screen.

    Platform-specific behavior:
        - Windows: Uses 'cls' command
        - Linux/macOS: Uses 'clear' command
    """
    os.system('cls' if sys.platform == 'win32' else 'clear')


def open_build_in_browser(build_url: str) -> None:
    """
    Open build URL in the default browser.

    Args:
        build_url: The URL of the Azure DevOps build to open in the browser.
    """
    webbrowser.open(build_url)


def main() -> None:
    """
    Main entry point for the pipeline watcher CLI.

    This function sets up the argument parser, handles command-line arguments,
    and routes execution to the appropriate subcommand handler (init or run).
    """
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Monitor Azure DevOps pipelines for the currently logged-in user"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Init command
    init_parser = subparsers.add_parser("init", help="Initialize configuration")
    init_parser.add_argument("--org", "-o", help="Azure DevOps organization name")
    init_parser.add_argument("--project", "-p", help="Azure DevOps project name")
    
    # Run command
    subparsers.add_parser("run", help="Run pipeline watcher (default)")
    
    args = parser.parse_args()
    
    if args.command == "init":
        init_config(organization=args.org, project=args.project)
        return
    elif args.command is None:
        # Default to run command
        run_watcher()
    elif args.command == "run":
        run_watcher()


def refresh_access_token_if_needed(credential: Any, org_name: str) -> str:
    """
    Refresh access token if it's about to expire or if we get a 401/403 error.
    
    Azure access tokens typically expire after 1 hour. We'll check if the token
    is close to expiring and refresh it if needed.
    
    Args:
        credential: The DefaultAzureCredential instance to use for token refresh.
        org_name: Azure DevOps organization name (for error messages).
    
    Returns:
        A valid access token string.
    """
    try:
        token = credential.get_token("499b84ac-1321-427f-aa17-267ca6975798/.default")
        return token.token
    except Exception as e:
        print(f"Warning: Failed to get/refresh Azure access token. Please run 'az login'.")
        print(f"Details: {e}")
        raise


def run_watcher() -> None:
    """
    Run the pipeline watcher.

    This function is the main execution loop of the pipeline watcher. It:
    1. Loads configuration from config.json
    2. Gets Azure DevOps organization and project settings
    3. Fetches the current user's access token
    4. Displays running and finished pipelines
    5. Enters an infinite polling loop to monitor for new pipelines

    The watcher continuously monitors for:
    - Running pipelines (displayed at each poll interval)
    - New finished pipelines (triggers notification sound)

    Note:
        This function runs indefinitely until interrupted by Ctrl+C.
    """
    config = load_config()
    
    azure_config = config.get("azure_devops", {})
    org_name = azure_config.get("organization")
    project_name = azure_config.get("project")
    
    # Get polling interval from config, default to 10 minutes
    polling_interval_minutes = config.get("polling_interval_minutes", 10)
    
    if not org_name or not project_name:
        print("Error: Organization and project must be specified in config.json")
        print("Please run 'pipeline-watcher init' first.")
        sys.exit(1)
    
    org_url = f"https://dev.azure.com/{org_name}"
    
    print(f"Azure DevOps Pipeline Watcher v{__version__}")
    print(f"Organization: {org_url}")
    print(f"Project: {project_name}")
    print(f"Polling Interval: {polling_interval_minutes} minutes")
    print("-" * 50)
    
    # Create credential once at the start
    credential = DefaultAzureCredential()
    
    # Get current user info first
    user_email, user_name = get_current_user_info()
    print(f"Current User: {user_email}")
    print("-" * 50)
    
    # Track seen pipeline IDs to detect new finished pipelines
    seen_pipeline_ids = set()
    
    # Get access token and display initial pipeline status
    try:
        access_token = get_access_token(credential)
    except Exception:
        sys.exit(1)
    
    # List running pipelines and display in tabular format
    running_pipelines = list_running_pipelines(org_name, project_name, access_token, user_email, user_name)
    display_pipelines_tabular(running_pipelines, title="Running", print_header=True, polling_interval_minutes=polling_interval_minutes)
    
    # Get finished pipelines from last 10 minutes
    finished_pipelines = list_finished_pipelines(org_name, project_name, access_token, user_email, user_name, minutes=30)
    for pipeline in finished_pipelines:
        seen_pipeline_ids.add(pipeline.get('id'))
    display_pipelines_tabular(finished_pipelines, title="Finished (Last 10 mins)", print_header=False, polling_interval_minutes=polling_interval_minutes)
    
    # Start polling loop (runs continuously to monitor both running and new finished pipelines)
    print(f"\nStarting poll loop (every {polling_interval_minutes} minutes). Press Ctrl+C to exit.\n")
    
    while True:
        time.sleep(polling_interval_minutes * 60)  # Convert minutes to seconds
        clear_screen()
        
        # Refresh access token if needed before making API calls
        try:
            access_token = refresh_access_token_if_needed(credential, org_name)
        except Exception:
            sys.exit(1)
        
        # Get finished pipelines from last 10 minutes
        finished_pipelines = list_finished_pipelines(org_name, project_name, access_token, user_email, user_name, minutes=30)
        
        # Check for new finished pipelines (those not in seen_pipeline_ids)
        new_finished_pipelines = []
        for pipeline in finished_pipelines:
            pipeline_id = pipeline.get('id')
            if pipeline_id not in seen_pipeline_ids:
                new_finished_pipelines.append(pipeline)
                seen_pipeline_ids.add(pipeline_id)
        
        # Play notification if new pipelines finished
        if new_finished_pipelines:
            print(f"\n{'=' * 50}")
            print(f"NOTIFICATION: New pipeline(s) finished!")
            print(f"{'=' * 50}")
            for pipeline in new_finished_pipelines:
                info = format_pipeline_info(pipeline)
                print(f"  - [{info['status'].upper()}] {info['name']} (ID: {info['id']})")
            print(f"{'=' * 50}\n")
            play_notification()
        
        # Re-fetch pipelines with fresh token
        running_pipelines = list_running_pipelines(org_name, project_name, access_token, user_email, user_name)
        display_pipelines_tabular(running_pipelines, title="Running", polling_interval_minutes=polling_interval_minutes)
        
        # Display all finished pipelines
        display_pipelines_tabular(finished_pipelines, title="Finished (Last 10 mins)", print_header=False, polling_interval_minutes=polling_interval_minutes)


if __name__ == "__main__":
    main()
