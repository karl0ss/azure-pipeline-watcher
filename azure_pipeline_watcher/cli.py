"""
Azure Pipeline Watcher - Monitor Azure DevOps pipelines.

This module provides the CLI interface for the pipeline watcher.
"""

import json
import os
import subprocess
import sys
import time
import webbrowser
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any
from dateutil.parser import isoparse
from tabulate import tabulate

import requests

from . import __version__


def get_config_dir() -> str:
    """Get the user's config directory."""
    home = os.path.expanduser("~")
    if sys.platform == "win32":
        return os.path.join(home, "AppData", "Local", "azure-pipeline-watcher")
    else:
        return os.path.join(home, ".config", "azure-pipeline-watcher")


def get_config_path() -> str:
    """Get the path to the config file."""
    return os.path.join(get_config_dir(), "config.json")


def load_config() -> Dict[str, Any]:
    """Load configuration from JSON file."""
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
    """Save configuration to JSON file."""
    config_dir = get_config_dir()
    os.makedirs(config_dir, exist_ok=True)
    config_path = get_config_path()
    with open(config_path, "w") as f:
        json.dump(config, f, indent=4)
    print(f"Configuration saved to {config_path}")


def init_config(organization: str = None, project: str = None) -> None:
    """Initialize configuration file interactively or with provided values."""
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
    """Play a notification sound based on platform."""
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


def get_access_token() -> str:
    """Get access token from Azure CLI."""
    try:
        use_shell = sys.platform == 'win32'
        result = subprocess.run(
            ["az", "account", "get-access-token", "--resource", "499b84ac-1321-427f-aa17-267ca6975798", "--out", "json"],
            capture_output=True,
            text=True,
            check=True,
            shell=use_shell
        )
        token_info = json.loads(result.stdout)
        return token_info["accessToken"]
    except subprocess.CalledProcessError as e:
        print("Error: Failed to get Azure access token. Please run 'az login' first.")
        print(f"Details: {e.stderr}")
        sys.exit(1)


def get_current_user_info() -> tuple[str, str]:
    """
    Get the email and username of the currently logged-in Azure user.
    Returns (email, username) tuple.
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


def parse_iso_datetime(value: str) -> datetime:
    """Parse ISO format datetime string."""
    if not value:
        return None
    return isoparse(value)


def list_running_pipelines(org_name: str, project: str, access_token: str, user_email: str, user_name: str) -> List[Dict[str, Any]]:
    """
    List all running pipelines in a project for the current user.
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
    Includes pipelines with any finished state (completed, succeeded, failed, cancelled, partiallySucceeded).
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
    if title == "Finished (Last 10 mins)":
        headers = ["#", "ID", "Name", "Status", "Finish Time", "Duration"]
    else:
        headers = ["#", "ID", "Name", "Status", "Duration"]
    table = tabulate(data, headers=headers, tablefmt="pipe")
    print(f"\n{table}")
    print()


def clear_screen() -> None:
    """Clear the terminal screen."""
    os.system('cls' if sys.platform == 'win32' else 'clear')


def open_build_in_browser(build_url: str) -> None:
    """Open build URL in default browser."""
    webbrowser.open(build_url)


def main() -> None:
    """Main entry point for the pipeline watcher CLI."""
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


def run_watcher() -> None:
    """Run the pipeline watcher."""
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
    
    # Get access token
    access_token = get_access_token()
    
    # Get current user info
    user_email, user_name = get_current_user_info()
    print(f"Current User: {user_email}")
    print("-" * 50)
    
    # Track seen pipeline IDs to detect new finished pipelines
    seen_pipeline_ids = set()
    
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
        
        # Re-fetch pipelines
        running_pipelines = list_running_pipelines(org_name, project_name, access_token, user_email, user_name)
        display_pipelines_tabular(running_pipelines, title="Running", polling_interval_minutes=polling_interval_minutes)
        
        # Display all finished pipelines
        display_pipelines_tabular(finished_pipelines, title="Finished (Last 10 mins)", print_header=False, polling_interval_minutes=polling_interval_minutes)


if __name__ == "__main__":
    main()
