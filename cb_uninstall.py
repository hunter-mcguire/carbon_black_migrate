#!/usr/local/bin/python3

import argparse
import csv

import requests


def uninstall_sensors(device_ids: list, cb_api_key: str, cb_url: str,
                      cb_org_key: str):
    resp = requests.post(
        url=f'{cb_url}/appservices/v6/orgs/{cb_org_key}/device_actions',
        json={'action_type': 'UNINSTALL_SENSOR', 'device_id': device_ids},
        headers={'X-AUTH-TOKEN': cb_api_key}
    )

    if resp:
        print('Uninstalled Sensors Initiated')

def validate_install(region: str, api_key: str, device_name: str) :
    url = f'https://workload.{region}.cloudone.trendmicro.com/api/computers/search?expand=none'
    headers = {'Authorization': f'ApiKey {api_key}', 'api-version': 'v1'}
    if "\\" in device_name:
        name = device_name.split('\\')[1]
    else:
        name = device_name
    search_response = requests.post(
                url=url,
                headers=headers,
                json={
                    'searchCriteria': [
                            {
                                'fieldName': 'hostName',
                                'stringTest': 'equal',
                                'stringValue': f"%{name}%" 
                            }
                        ]
                    }
            )
    response = search_response.json().get('computers')

    if response:
        print(f'{name} found in Cloud One')
        return True

if __name__ == '__main__':

    parser = argparse.ArgumentParser(
        prog='AgentInstall',
        description='Script to Uninstall Carbon Black Agent'
    )

    parser.add_argument('--trend_api_key', required=True)
    parser.add_argument('--trend_region', required=True)
    parser.add_argument('--cb_api_key', required=True)
    parser.add_argument('--cb_url', required=True)
    parser.add_argument('--cb_org_key', required=True)
    parser.add_argument('--deployment_csv', required=True)
    parser.add_argument('--verbose', required=False, action="store_true",
                        help='Log progress output in terminal.')
    
    # Parse args to collect param values
    args = parser.parse_args()

    # List of devices found in Cloud One to uninstall
    uninstall_list = []

    # open devices csv
    try:
        with open(args.deployment_csv, 'r') as csv_file:
            reader = csv.DictReader(csv_file)

            if reader:
                '''
                Iterate through devices.
                    - If found in Workload Security, add to uninstall_list
                    - uninstall Carbon Black sensors found in Workload Security
                '''
                for device in reader:
                    device_name = device.get('device_name')
                    if device.get('status') == 'install_process_started':
                        if validate_install(
                            api_key=args.trend_api_key,
                            region=args.trend_region,
                            device_name=device_name
                        ):
                            device_id = device.get('device_id')
                            if device_id:
                                uninstall_list.append(str(device_id))
                if uninstall_list:
                    uninstall_sensors(
                        device_ids=[device for device in uninstall_list],
                        cb_api_key=args.cb_api_key,
                        cb_url=args.cb_url,
                        cb_org_key=args.cb_org_key
                    )
                else:
                    print('None found in Cloud One')
    except Exception as error:
        print(error)
        print('Failed to load CSV file for agent_deployment.csv')

#'av_status': ['AV_DEREGISTERED']

    
