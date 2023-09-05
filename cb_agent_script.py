import argparse
import csv
from datetime import datetime
import json
import time

from jinja2 import Environment, BaseLoader
import requests

CSV_COLUMNS = ('name', 'status', 'timestamp', 'device_id')
CSV_FILEPATH = 'agent_deployment.csv'

def search_devices(url: str, cb_org_key: str, headers: dict,
                   os_type: list):
    url = f'{url}/appservices/v6/orgs/{cb_org_key}/devices/_search'
    payload = {'criteria': {'os': os_type}}
    resp = requests.post(url, data=payload, headers=headers)

    return resp

class DeviceSession:
    def __init__(self, device_id: int, cb_url: str, cb_api_key: str,
                 cb_org_key: str) -> None:
        self.device_id = device_id
        self.cb_url = cb_url
        self.cb_org_key = cb_org_key
        self.headers = {'X-AUTH-TOKEN': cb_api_key}
        self.session_id = self.start_device_session()

    def start_device_session(self):
        '''
        Function for acquiring live response session to devicw
        '''
        url = f'{self.cb_url}/appservices/v6/orgs/{self.cb_org_key}/liveresponse/sessions'
        payload = {'device_id': self.device_id}
        resp = requests.post(url, json=payload, headers=self.headers)

        return resp.json().get('id')

    def get_device_info(self):
        '''
        Function for getting device info
        '''
        resp = requests.get(
            f'{self.cb_url}/appservices/v6/orgs/{self.cb_url}/devices/{self.device_id}',
            headers=self.headers
        )

        return resp.json()

    def file_upload(self, display_name: str, policy_id: int):
        '''
        Function for uploading agent install script to Carbon Black Cloud
        '''
        data = {
            'display_name': display_name,
            'policy_id': policy_id
        }

        with open('trend_activation.ps1') as file:
            rtemplate = Environment(loader=BaseLoader).from_string(file.read())
            data = rtemplate.render(**data).encode('utf-8')

        url = f'{self.cb_url}/appservices/v6/orgs/{self.cb_org_key}/liveresponse/sessions/{self.session_id}/files'
        resp = requests.post(
            url,
            files=data,
            headers=self.headers
        )

        return resp.json().get('id')

    def put_file(self, file_id: str):
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
        resp = requests.post(url, json=payload, headers=self.headers)

        return resp.json()

    def create_process(self, output_file: str = 'c:\\temp\install.log'):
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
        
        resp = requests.post(url, json=payload, headers=self.headers)
        if resp:
            return resp.json().get('id')

    def check_cmd_status(self, cmd_id: str):
        '''
        Function for checking status of live response action. Requires Id from response.
        '''
        url = f'{self.cb_url}/appservices/v6/orgs/{self.cb_org_key}/liveresponse/sessions/{self.session_id}/commands/{cmd_id}'
        resp = requests.get(url, headers=self.headers).json()

        if resp.get('status') == 'COMPLETE':
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
    parser.add_argument('--verbose', required=False,
                        help='Log progress output in terminal.')
    

    def main(device_ids: list):
        # Create CSV file for logging deployment
        with open(CSV_FILEPATH, 'w') as file:
            writer = csv.DictWriter(file, fieldnames=CSV_COLUMNS)
            writer.writeheader()

        # Iterate through all devices. 
        # Acquire session, push install script to deviCE and create process
        for device_id in device_ids:
            try:
                device_session = DeviceSession(
                    device_id=device_id,
                    cb_api_key=args.cb_api_key,
                    cb_url=args.cb_url,
                    cb_org_key=args.cb_org_key
                )
                if not device_session.session_id:
                    print(f'ERROR: Failed to get session for device: {device_id}')
                    with open(CSV_FILEPATH, 'a') as file:
                        writer = csv.DictWriter(file, fieldnames=CSV_COLUMNS)
                        writer.writerow(
                            {
                                'device_id': device_id,
                                'status': 'session_attempt_failed',
                                'timestamp': datetime.now().isoformat()
                            }
                        )
                    continue

                status = 'session_started'
                device_name = device_session.get_device_info().get('name')

                if args.verbose:
                    print(f'{status} on device: {device_name}')

                file_id = device_session.file_upload(
                    display_name=device_name,
                    policy_id=args.ws_policy_id
                )
                status = 'file_upload_attempted'

                if args.verbose:
                    print(f'{status} on device: {device_name}')
                time.sleep(.5)

                if file_id:
                    put_file = json.loads(device_session.put_file(file_id))
                    status = 'put_file_attempted'
                    if args.verbose:
                        print(f'{status} on device: {device_name}')
                    time.sleep(.5)

                if put_file:
                    process = device_session.create_process()
                    status = 'install_process_attempted'
                    if args.verbose:
                        print(f'{status} on device: {device_name}')

                if process:
                    status = 'install_started'
                    if process and args.verbose:
                        print(f'{status} on device: {device_id}')

                with open(CSV_FILEPATH, 'a') as file:
                    writer = csv.DictWriter(file, fieldnames=CSV_COLUMNS)
                    writer.writerow(
                        {
                            'name': device_name,
                            'status': status,
                            'timestamp': datetime.now().isoformat()
                        }
                    )
            except Exception as error:
                print(f'ERROR: {error}')

    # Parse args to collect param values
    args = parser.parse_args()

    # device_id param
    if args.device_ids:
        assert not args.device_ids_csv
        # Run Main Function
        main(device_ids=args.device_ids)

    # device_ids_csv param
    if args.device_ids_csv:
        assert not args.device_ids
        try:
            with open(args.device_ids_csv) as csv_file:
                reader = csv.DictReader(csv_file)
        except Exception as error:
            print('Failed to load CSV file for device IDs')

        if reader:
            # Run Main Function
            main(device_ids=[row['deviceId'] for row in reader])