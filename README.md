# AWS EC2 Resource Monitor

A Python script to monitor disk and RAM usage across multiple EC2 instances based on their Name tags. The script provides a clear tabular view of resource utilization and alerts for instances exceeding defined thresholds.

## Features

- Monitor multiple EC2 instances simultaneously
- Filter instances by Name tags
- Track disk and RAM usage
- Visual alerts for resource threshold breaches
- Support for comma-separated or newline-separated instance tags
- Region-specific monitoring
- Colorized output for better visibility

## Prerequisites

1. Python 3.6 or higher
2. AWS credentials configured
3. Required Python packages:
   - boto3
   - prettytable

## Installation
1. Install required packages
```bash
pip install -r requirements.txt
```

## Configuration

1. Create a file named `instance_tags.txt` in the same directory as the script
2. Add EC2 instance Name tags to monitor (one per line or comma-separated):
e.g.
```
web-server-1
web-server-2
```
3. (Optional) Modify thresholds in the script:
```python
DISK_THRESHOLD = 80  # Disk usage threshold percentage
RAM_THRESHOLD = 80   # RAM usage threshold percentage
```

## Usage
1. Set AWS region (optional):
```bash
export AWS_REGION=us-west-2
```
2. Run the script:
```bash
python main.py
```

## Output Example
```
Monitoring EC2 instances in region: us-west-2

Instance Resource Usage:
+---------------------+--------------+----------------+---------------+--------+
|     Instance ID     |     Name     | Disk Usage (%) | RAM Usage (%) | Status |
+---------------------+--------------+----------------+---------------+--------+
| i-0a45ae23620edc9d4 | web-server-1 |      20%       |      14%      | ALERT  |
| i-01e51ef9821116b29 | web-server-2 |      20%       |      14%      | ALERT  |
| i-017aca45f9748fc0a | web-server-3 |      20%       |      14%      | ALERT  |
+---------------------+--------------+----------------+---------------+--------+

⚠️  ALERTS - Instances Exceeding Thresholds:

Disk Usage >= 15%:
  • web-server-1 (i-0a45ae23620edc9d4): 20%
  • web-server-2 (i-01e51ef9821116b29): 20%
  • web-server-3 (i-017aca45f9748fc0a): 20%
```
