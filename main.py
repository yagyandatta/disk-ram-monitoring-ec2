import boto3
from prettytable import PrettyTable
import time
import os
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm
import threading

# AWS Region Configuration
AWS_REGION = os.getenv('AWS_REGION', 'us-west-2')  # Default to us-west-2 if not specified
MAX_THREADS = 10  # Maximum number of concurrent threads

# Initialize boto3 clients with region
ec2 = boto3.client('ec2', region_name=AWS_REGION)
ssm = boto3.client('ssm', region_name=AWS_REGION)

# Thread-local storage for boto3 clients
thread_local = threading.local()

# Set thresholds
DISK_THRESHOLD = 15  # Disk usage threshold percentage
RAM_THRESHOLD = 80   # RAM usage threshold percentage
TAG_FILE_PATH = 'instance_tags.txt'  # File containing instance tags

def get_thread_ssm_client():
    """Get thread-local SSM client"""
    if not hasattr(thread_local, 'ssm'):
        thread_local.ssm = boto3.client('ssm', region_name=AWS_REGION)
    return thread_local.ssm

def read_instance_tags():
    """Read instance tags from the text file."""
    try:
        with open(TAG_FILE_PATH, 'r') as file:
            # Read tags and remove empty lines and whitespace
            tags = [tag.strip() for tag in file.read().replace(',', '\n').splitlines() if tag.strip()]
        return tags
    except FileNotFoundError:
        print(f"Error: {TAG_FILE_PATH} not found")
        return []

def get_instance_ids_with_tags():
    """Get EC2 instance IDs for specified tags."""
    tags = read_instance_tags()
    if not tags:
        print("No tags provided in the file")
        return []

    instance_info = []
    try:
        instances = ec2.describe_instances(
            Filters=[
                {'Name': 'instance-state-name', 'Values': ['running']},
                {'Name': 'tag:Name', 'Values': tags}
            ]
        )
        
        for reservation in instances['Reservations']:
            for instance in reservation['Instances']:
                instance_id = instance['InstanceId']
                name = None
                for tag in instance.get('Tags', []):
                    if tag['Key'] == 'Name':
                        name = tag['Value']
                instance_info.append({'InstanceId': instance_id, 'Name': name})
        return instance_info
    except Exception as e:
        print(f"Error fetching instances: {str(e)}")
        return []

def get_disk_and_memory_usage(instance_info):
    """Execute command on instance to get disk and memory usage."""
    instance_id = instance_info['InstanceId']
    name = instance_info['Name']
    ssm_client = get_thread_ssm_client()
    
    try:
        command = "df -h --output=pcent / | tail -n 1 && free -m | awk '/Mem:/ {printf(\"%d\", $3*100/$2)}'"
        response = ssm_client.send_command(
            InstanceIds=[instance_id],
            DocumentName="AWS-RunShellScript",
            Parameters={'commands': [command]}
        )
        command_id = response['Command']['CommandId']

        # Wait for command to complete with timeout
        max_retries = 10
        for _ in range(max_retries):
            time.sleep(2)
            output = ssm_client.get_command_invocation(CommandId=command_id, InstanceId=instance_id)
            if output['Status'] in ['Success', 'Failed']:
                break
        
        if output['Status'] == 'Success':
            results = output['StandardOutputContent'].strip().splitlines()
            disk_usage = int(results[0].strip('%'))
            ram_usage = int(results[1])
            return {
                'InstanceId': instance_id,
                'Name': name,
                'disk_usage': disk_usage,
                'ram_usage': ram_usage,
                'status': 'Success'
            }
    except Exception as e:
        print(f"\nError getting metrics for instance {instance_id}: {str(e)}")
    
    return {
        'InstanceId': instance_id,
        'Name': name,
        'disk_usage': None,
        'ram_usage': None,
        'status': 'Error'
    }

def monitor_ec2_resources():
    try:
        print(f"\nMonitoring EC2 instances in region: {AWS_REGION}")
        instance_info = get_instance_ids_with_tags()
        
        if not instance_info:
            print("No instances found to monitor.")
            return

        # Create progress bar
        print("\nCollecting metrics from instances...")
        results = []
        
        # Use ThreadPoolExecutor for parallel processing
        with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
            futures = [executor.submit(get_disk_and_memory_usage, info) for info in instance_info]
            
            # Create progress bar
            with tqdm(total=len(futures), desc="Progress", unit="instance") as pbar:
                for future in futures:
                    results.append(future.result())
                    pbar.update(1)

        # Set up table with headers
        table = PrettyTable()
        table.field_names = ["Instance ID", "Name", "Disk Usage (%)", "RAM Usage (%)", "Status"]
        
        # Lists to store instances exceeding thresholds
        disk_alerts = []
        ram_alerts = []
        
        # Process results and build table
        for result in results:
            instance_id = result['InstanceId']
            name = result['Name'] or "Unnamed"
            disk_usage = result['disk_usage']
            ram_usage = result['ram_usage']
            
            if disk_usage is None or ram_usage is None:
                status = "Error"
                disk_display = "N/A"
                ram_display = "N/A"
            else:
                status = "OK"
                if disk_usage >= DISK_THRESHOLD or ram_usage >= RAM_THRESHOLD:
                    status = "\033[91mALERT\033[0m"
                
                if disk_usage >= DISK_THRESHOLD:
                    disk_alerts.append((name, instance_id, disk_usage))
                    disk_display = f"\033[91m{disk_usage}%\033[0m"
                else:
                    disk_display = f"{disk_usage}%"
                
                if ram_usage >= RAM_THRESHOLD:
                    ram_alerts.append((name, instance_id, ram_usage))
                    ram_display = f"\033[91m{ram_usage}%\033[0m"
                else:
                    ram_display = f"{ram_usage}%"
            
            table.add_row([instance_id, name, disk_display, ram_display, status])
        
        # Print results
        print("\nInstance Resource Usage:")
        print(table)
        
        if disk_alerts or ram_alerts:
            print("\n⚠️  ALERTS - Instances Exceeding Thresholds:")
            
            if disk_alerts:
                print(f"\nDisk Usage >= {DISK_THRESHOLD}%:")
                for name, instance_id, usage in disk_alerts:
                    print(f"  • {name} ({instance_id}): {usage}%")
            
            if ram_alerts:
                print(f"\nRAM Usage >= {RAM_THRESHOLD}%:")
                for name, instance_id, usage in ram_alerts:
                    print(f"  • {name} ({instance_id}): {usage}%")
                    
    except Exception as e:
        print(f"Error monitoring EC2 resources: {str(e)}")

# Run the monitoring function
if __name__ == "__main__":
    monitor_ec2_resources()
