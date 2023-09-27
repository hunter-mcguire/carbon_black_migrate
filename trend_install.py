#!/usr/local/bin/python3

import argparse
import csv
from datetime import datetime
import time

from jinja2 import Environment, BaseLoader
import requests

CSV_COLUMNS = ('device_name', 'device_id', 'status', 'timestamp')
CSV_FILEPATH = f"agent_deployment-{datetime.now().isoformat('-', 'seconds')}.csv"
DEPLOY_LIST = []


class DeviceSession:
    def __init__(self, device_id: int, cb_url: str, cb_api_key: str,
                 cb_org_key: str) -> None:
        self.device_id = device_id
        self.cb_url = cb_url
        self.cb_org_key = cb_org_key
        self.headers = {'X-AUTH-TOKEN': cb_api_key}
        self.file_id = None
        self.status = None
        self.device_name = self.get_device_name()
        self.session_id = self.start_device_session()

    def start_device_session(self):
        '''
        Function for acquiring live response session to device
        '''
        url = f'{self.cb_url}/appservices/v6/orgs/{self.cb_org_key}/liveresponse/sessions'
        payload = {'device_id': self.device_id}
        response = requests.post(url, json=payload, headers=self.headers)
        if response:
            return response.json().get('id')

    def get_device_name(self):
        '''
        Function for getting device info
        '''
        response = requests.get(
            f'{self.cb_url}/appservices/v6/orgs/{self.cb_org_key}/devices/{self.device_id}',
            headers=self.headers
        )

        if response:
            return response.json().get('name')

    def file_upload(self, data: bytes) -> int:
        '''
        Function for uploading agent install script to Carbon Black Cloud
        '''

        url = f'{self.cb_url}/appservices/v6/orgs/{self.cb_org_key}/liveresponse/sessions/{self.session_id}/files'
        response = requests.post(
            url,
            files={'file': data},
            headers=self.headers
        )

        if response:
            return response.json().get('id')

    def put_file(self, file_id: str) -> bool:
        '''
        Function for putting previously loaded file to device
        '''
        path = 'c:\\temp\\trend_install.ps1'
        payload = {
            'name': 'put file',
            'path': path,
            'file_id': file_id
        }
        url = f'{self.cb_url}/appservices/v6/orgs/{self.cb_org_key}/liveresponse/sessions/{self.session_id}/commands'

        response = requests.post(url, json=payload, headers=self.headers)

        if response:
            _id = response.json().get('id')
            retry = 0
            while retry < 5:
                if self.check_cmd_status(_id):
                    return True
                retry +=1
                time.sleep(1)

    def create_process(self, output_file: str = 'c:\\temp\\install.log'):
        '''
        Function to create process / start Trend installation on device
        '''
        path = 'c:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe -ExecutionPolicy Bypass -File c:\\temp\\trend_install.ps1'
        url = f'{self.cb_url}/appservices/v6/orgs/{self.cb_org_key}/liveresponse/sessions/{self.session_id}/commands'
        payload = {
            'name': 'create process',
            'path': path,
            'output_file': output_file
        }
        
        response = requests.post(url, json=payload, headers=self.headers)

        if response:
            return response.json().get('id')

    def check_cmd_status(self, cmd_id: str) -> bool:
        '''
        Function for checking status of live response action. Requires Id from live session response.
        '''
        url = f'{self.cb_url}/appservices/v6/orgs/{self.cb_org_key}/liveresponse/sessions/{self.session_id}/commands/{cmd_id}'

        response = requests.get(url, headers=self.headers)

        if response:
            if response.json().get('status') == 'COMPLETE':
                return True

if __name__ == '__main__':
    '''
    Main function used if running as commandline program.
    '''

    parser = argparse.ArgumentParser(
        prog='AgentInstall',
        description='Script to install Trend Micro Agent'
    )

    parser.add_argument('--cb_api_key', required=True)
    parser.add_argument('--cb_url', required=True)
    parser.add_argument('--cb_org_key', required=True)
    parser.add_argument('--ws_policy_id', required=True,
                        help='Workload Security PolicyID to assign to agents')
    parser.add_argument('--device_ids', nargs='+', required=False,
                        help='1+ IDs with space between. ex. --device_ids 5765373 8765373')
    parser.add_argument('--device_ids_csv', required=False,
                        help='Path to a CSV file containing device_ids in a column named deviceId.')
    parser.add_argument('--verbose', required=False, action="store_true",
                        help='Log progress output in terminal.')

    # Parse args to collect param values
    args = parser.parse_args()

    def main(device_ids: list):
        # Iterate through all devices. 
        # Acquire session, push install script to device and create process
        with open('trend_install.ps1') as file:
            rtemplate = Environment(loader=BaseLoader).from_string(file.read())
            file_data = rtemplate.render({'policy_id': args.ws_policy_id}).encode('utf-8')

        for device_id in device_ids:
            device_session = DeviceSession(
                device_id=device_id,
                cb_api_key=args.cb_api_key,
                cb_url=args.cb_url,
                cb_org_key=args.cb_org_key,
            )

            if not device_session.session_id:
                device_session.status = 'session_attempt_failed'
                if args.verbose:
                    print(f'{device_session.status} on device: {device_session.device_name}')
                DEPLOY_LIST.append(device_session)
                continue

            device_session.status = 'session_started'

            if args.verbose:
                print(f'{device_session.status} on device: {device_session.device_name}')

            device_session.file_id = device_session.file_upload(
                data=file_data
            )
        
            device_session.status = 'file_upload_attempted' if device_session.file_id else 'file_upload_failed'

            if args.verbose:
                print(f'{device_session.status} on device: {device_session.device_name}')

            DEPLOY_LIST.append(device_session)

        #sleep for 1 minute to wait for completion of file uploads
        print('File Uploads Complete. Sleeping for 1 minute...')
        time.sleep(60)

        # Iterate through successful file uploads and move file, install
        for device in DEPLOY_LIST:
            if device.status == 'file_upload_attempted':
                put_file = device.put_file(device.file_id)
                device.status = 'put_file_attempted' if put_file else 'put_file_failed'

                if args.verbose:
                    print(f'{device.status} on device: {device.device_name}')

                if put_file:
                    process = device.create_process()
                    device.status = 'install_process_started' if process else 'install_process_failed'
                    if args.verbose:
                        print(f'{device.status} on device: {device.device_name}')

                with open(CSV_FILEPATH, 'a') as file:
                    writer = csv.DictWriter(file, fieldnames=CSV_COLUMNS)
                    writer.writerow(
                        {
                            'device_name': device.device_name,
                            'device_id':  str(device_id),
                            'status': device.status,
                            'timestamp': datetime.now().isoformat(' ', 'seconds')
                        }
                    )
try:
    # CSV file creation
    # CSV for writing progress
    with open(CSV_FILEPATH, 'w') as file:
        writer = csv.DictWriter(file, fieldnames=CSV_COLUMNS)
        writer.writeheader()

    #csv param
    if args.device_ids_csv:
        with open(args.device_ids_csv, 'r') as csv_file:
            reader = csv.DictReader(csv_file)
            device_ids=[row['deviceId'] for row in reader]
        assert not args.device_ids
        main(device_ids)

    # device_id param
    if args.device_ids:
        assert not args.device_ids_csv
        # Run Main Function
        main(args.device_ids)

except AssertionError:
    print("Must use either 'device_ids' or 'device_ids_csv' params, not both.")

