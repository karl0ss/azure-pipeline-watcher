# Azure DevOps Pipeline Watcher

A Python application that monitors running and recently finished pipelines for the currently logged-in user in Azure DevOps.

## Prerequisites

1. Python 3.8 or higher
2. Azure CLI installed and logged in (`az login`)
3. Azure DevOps access

## Installation

1. Clone or copy the project files
2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Configuration

Update the `config.json` file with your Azure DevOps organization and project:

```json
{
    "azure_devops": {
        "organization": "your-organization-name",
        "project": "your-project-name",
        "polling_interval_minutes": 5
    }
}
```

Optional `polling_interval_minutes` (default: 5) - Time in minutes between each poll of the pipeline status.

## Usage

1. Make sure you're logged into Azure CLI:
```bash
az login
```

2. Run the application:
```bash
python pipeline_watcher.py
```

## Features

- Shows all running pipelines for the current user
- Shows recently finished pipelines from the last 10 minutes
- Displays pipeline name, ID, status, requester, start time, and duration
- Uses Azure CLI authentication for seamless login
- Filters pipelines by the currently logged-in user
- Clickable build IDs in output (click to open in browser)
- Continuous polling loop with configurable interval
- Tabular output format

## Output Example

```
Azure DevOps Pipeline Watcher
Organization: https://dev.azure.com/myorg
Project: myproject
Polling Interval: 5 minutes
--------------------------------------------------
Current User: user@example.com
--------------------------------------------------

Last poll: 2026-03-28 11:40:20
--- Running Pipelines ---

# | ID | Name | Status | Duration
-- | -- | ---- | ------ | --------
1 | [12345](https://dev.azure.com/myorg/myproject/_build/results?buildId=12345) | Build and Test | inProgress | 4:50:40
2 | [12346](https://dev.azure.com/myorg/myproject/_build/results?buildId=12346) | Deploy to Prod | inProgress | 1:26:32

--- Finished (Last 10 mins) ---

# | ID | Name | Status | Finish Time | Duration
-- | -- | ---- | ------ | ----------- | --------
1 | [12340](https://dev.azure.com/myorg/myproject/_build/results?buildId=12340) | Build PR #42 | succeeded | 10:35:22 | 0:15:33

Total running pipelines: 2
Total finished pipelines (last 10 mins): 1
```
