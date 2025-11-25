#!/bin/bash

echo "================================================================================"
echo "PRODUCTION ASYNC STATS CHECK"
echo "================================================================================"
echo ""

curl -s "https://ngrssolver08.comcentricapps.com/solve/async/stats?details=true" | python3 << 'PYTHON_SCRIPT'
import sys
import json
from datetime import datetime

data = json.load(sys.stdin)

print("QUEUE STATUS:")
print(f"  Queued Jobs:        {data.get('queued', 'N/A')}")
print(f"  Processing Jobs:    {data.get('processing', 'N/A')}")
print(f"  Completed Jobs:     {data.get('completed', 'N/A')}")
print(f"  Failed Jobs:        {data.get('failed', 'N/A')}")
print()
print("WORKER STATUS:")
print(f"  Total Workers:      {data.get('workers', 'N/A')}")
print(f"  Active Workers:     {data.get('active_workers', 'N/A')}")
print()
print("SYSTEM:")
print(f"  Uptime:            {data.get('uptime', 'N/A')}")
print(f"  Redis Connected:   {data.get('redis_connected', 'N/A')}")
print()
print("===============================================================================")

# Check for concerning states
total_active = data.get('queued', 0) + data.get('processing', 0)
if total_active > 20:
    print(f"⚠️  WARNING: High job count detected ({total_active} active jobs)")
    print("   This may indicate:")
    print("   - Jobs are taking longer than expected")
    print("   - Queue is backing up")
    print("   - Workers may need scaling")
elif total_active > 10:
    print(f"ℹ️  NOTICE: Moderate job count ({total_active} active jobs)")
else:
    print(f"✅ Normal operation ({total_active} active jobs)")

print()

# Display detailed job list if available
if 'jobs' in data and data['jobs']:
    print("===============================================================================")
    print(f"DETAILED JOB LIST ({len(data['jobs'])} jobs)")
    print("===============================================================================")
    print()
    
    for job in data['jobs'][:20]:  # Show first 20 jobs
        job_id = job['job_id']
        status = job['status']
        created = job.get('created_at', 'N/A')
        updated = job.get('updated_at', 'N/A')
        has_result = '✓' if job.get('has_result') else '✗'
        
        # Format timestamps if available
        if created != 'N/A':
            try:
                created_dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                created = created_dt.strftime('%Y-%m-%d %H:%M:%S')
            except:
                pass
        
        if updated != 'N/A':
            try:
                updated_dt = datetime.fromisoformat(updated.replace('Z', '+00:00'))
                updated = updated_dt.strftime('%Y-%m-%d %H:%M:%S')
            except:
                pass
        
        status_icon = {'completed': '✓', 'failed': '✗', 'queued': '⏳', 'in_progress': '⚙️'}.get(status, '•')
        
        print(f"{status_icon} {status:12s} | {job_id}")
        print(f"   Created:  {created}")
        print(f"   Updated:  {updated}")
        print(f"   Result:   {has_result}")
        print()
    
    if len(data['jobs']) > 20:
        print(f"... and {len(data['jobs']) - 20} more jobs")
        print()

print("===============================================================================")

PYTHON_SCRIPT

echo ""
echo "================================================================================"
