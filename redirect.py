import json
import boto3
from datetime import datetime
from datetime import timedelta  
import time
cache = {}

def lambda_handler(event, context):
    client = boto3.client('lambda')
    requested_ts = event["path"][1:]

    if requested_ts in cache:
        if datetime.now() > cache[requested_ts]['time']:
            print("fetching")
            cache[requested_ts]['url'] = client.get_function(FunctionName='bbb-' + requested_ts)['Code']['Location']
            cache[requested_ts]['time'] = datetime.now() + timedelta(minutes=5)
    else:
        print("fetching")
        cache[requested_ts]={}
        cache[requested_ts]['url'] = client.get_function(FunctionName='bbb-' + requested_ts)['Code']['Location']
        cache[requested_ts]['time'] = datetime.now() + timedelta(minutes=5)
    redirect_url = cache[requested_ts]['url']
    return {
        'statusCode': 302,
        'headers': {
            "Location": redirect_url
        },
        'body': redirect_url
    }

#test locally
if __name__ == "__main__":
    lambda_handler({"path":"/3"},None) 
    lambda_handler({"path":"/3"},None)
    time.sleep(10)
    lambda_handler({"path":"/3"},None)