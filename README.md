# Azure DevOps Pipeline Watcher

A Python application that monitors running and recently finished pipelines for the currently logged-in user in Azure DevOps.

## Prerequisites

1. Python 3.8 or higher
2. Azure CLI installed and logged in (`az login`)
3. Azure DevOps access

## Installation

### Using pip (Recommended)

Install directly from GitHub:

```bash
pip install git+https://github.com/karl0ss/azure-pipeline-watcher.git
```

Or clone the repository and install locally:

```bash
git clone https://github.com/karl0ss/azure-pipeline-watcher.git
cd azure-pipeline-watcher
pip install .
```

### First-time Setup

After installation, initialize the configuration:

```bash
azure-pipeline-watcher init --org your-organization-name --project your-project-name
```

Or run interactively:

```bash
azure-pipeline-watcher init
```

This will create a configuration file at:
- **Linux/macOS**: `~/.config/azure-pipeline-watcher/config.json`
- **Windows**: `%LOCALAPPDATA%\azure-pipeline-watcher\config.json`

## Configuration

The configuration file is automatically created at `azure-pipeline-watcher init`. You can edit it manually:

```json
{
    "azure_devops": {
        "organization": "your-organization-name",
        "project": "your-project-name"
    },
    "polling_interval_minutes": 10
}
```

Optional `polling_interval_minutes` (default: 10) - Time in minutes between each poll of the pipeline status.

## Usage

1. Make sure you're logged into Azure CLI:
```bash
az login
```

2. Run the pipeline watcher:
```bash
azure-pipeline-watcher run
```

Or simply:
```bash
azure-pipeline-watcher
```

## Features

- Shows all running pipelines for the current user
- Shows recently finished pipelines from the last 30 minutes
- Shows pipeline name, ID, status, requester, start time, finish time, and duration
- Uses Azure CLI authentication for seamless login
- Filters pipelines by the currently logged-in user
- Clickable build IDs in output (click to open in browser)
- Continuous polling loop with configurable interval
- Tabular output format
- **Auto-detects new finished pipelines** - Highlights pipelines that finished since the last poll
- **Notification sound** - Plays a platform-specific sound when new pipelines finish (Windows: `.wav`, macOS: system sounds, Linux: `.ogg`/`.wav`)
- **Clear screen on each poll** - Refreshes the display for a clean view
- **Configurable polling interval** - Set via `polling_interval_minutes` in config
- **Interactive init command** - Setup can be done interactively or with command-line arguments

## Output Example

```
Azure DevOps Pipeline Watcher v1.0.0
Organization: https://dev.azure.com/myorg
Project: myproject
Polling Interval: 10 minutes
--------------------------------------------------
Current User: user@example.com
---

Next poll: 2026-03-28 11:40:20
--- Running Pipelines ---

# | ID | Name | Status | Duration | Finish Time
-- | -- | ---- | ------ | -------- | -----------
1 | [12345](https://dev.azure.com/myorg/myproject/_build/results?buildId=12345) | Build and Test | inProgress | 4:50:40 |
2 | [12346](https://dev.azure.com/myorg/myproject/_build/results?buildId=12346) | Deploy to Prod | inProgress | 1:26:32 |

--- Finished (Last 30 mins) ---

# | ID | Name | Status | Finish Time | Duration
-- | -- | ---- | ------ | ----------- | --------
1 | [12340](https://dev.azure.com/myorg/myproject/_build/results?buildId=12340) | Build PR #42 | succeeded | 10:35:22 | 0:15:33

Total running pipelines: 2
Total finished pipelines (last 30 mins): 1
```
