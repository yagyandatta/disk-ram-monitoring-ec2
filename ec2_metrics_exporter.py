from flask import Flask, Response
import boto3
import time
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST, Gauge, CollectorRegistry
import threading
import os

# AWS Region Configuration
AWS_REGION = os.getenv('AWS_REGION', 'us-west-2')

# Initialize boto3 clients
ec2 = boto3.client('ec2', region_name=AWS_REGION)
ssm = boto3.client('ssm', region_name=AWS_REGION)

# Create Flask app
app = Flask(__name__)

# Create a custom registry
registry = CollectorRegistry()

# Define Prometheus metrics
disk_usage = Gauge('ec2_disk_usage_percent', 
                  'Disk usage percentage', 
                  ['instance_id', 'instance_name'],
                  registry=registry)
memory_usage = Gauge('ec2_memory_usage_percent', 
                    'Memory usage percentage', 
                    ['instance_id', 'instance_name'],
                    registry=registry)

def get_instance_metrics():
    """Collect metrics from EC2 instances"""
    try:
        # Get running instances
        instances = ec2.describe_instances(
            Filters=[{'Name': 'instance-state-name', 'Values': ['running']}]
        )

        for reservation in instances['Reservations']:
            for instance in reservation['Instances']:
                instance_id = instance['InstanceId']
                instance_name = "Unknown"
                
                # Get instance name from tags
                for tag in instance.get('Tags', []):
                    if tag['Key'] == 'Name':
                        instance_name = tag['Value']

                try:
                    # Get disk and memory metrics
                    command = "df -h --output=pcent / | tail -n 1 && free -m | awk '/Mem:/ {printf(\"%d\", $3*100/$2)}'"
                    response = ssm.send_command(
                        InstanceIds=[instance_id],
                        DocumentName="AWS-RunShellScript",
                        Parameters={'commands': [command]}
                    )
                    
                    command_id = response['Command']['CommandId']
                    time.sleep(2)  # Wait for command execution
                    
                    output = ssm.get_command_invocation(
                        CommandId=command_id,
                        InstanceId=instance_id
                    )
                    
                    if output['Status'] == 'Success':
                        results = output['StandardOutputContent'].strip().splitlines()
                        disk_percent = float(results[0].strip('%'))
                        memory_percent = float(results[1])
                        
                        # Update Prometheus metrics
                        disk_usage.labels(instance_id=instance_id, 
                                       instance_name=instance_name).set(disk_percent)
                        memory_usage.labels(instance_id=instance_id, 
                                         instance_name=instance_name).set(memory_percent)
                
                except Exception as e:
                    print(f"Error collecting metrics for instance {instance_id}: {str(e)}")
                    
    except Exception as e:
        print(f"Error in get_instance_metrics: {str(e)}")

@app.route('/metrics')
def metrics():
    """Endpoint for Prometheus metrics"""
    get_instance_metrics()
    return Response(generate_latest(registry), mimetype=CONTENT_TYPE_LATEST)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9100)
