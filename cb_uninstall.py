import argparse
import csv

import requests


if __name__ == '__main__':

    parser = argparse.ArgumentParser(
        prog='AgentInstall',
        description='Script to install Trend Micro Agent'
    )

    parser.add_argument('--cb_api_key', required=True)
    parser.add_argument('--cb_url', required=True)
    parser.add_argument('--cb_org_key', required=True)
    parser.add_argument('--cloud_one_api_key', required=True)
    
    parser.add_argument('--device_ids', nargs='+', required=False,
                        help='Migrate multiple DS agents. 1+ IDs with space between. ex.  --device_ids 32 33')
    parser.add_argument('--device_ids_csv', required=False,
                        help='Path to a CSV file containing device_ids in a column named deviceId.')
    parser.add_argument('--verbose', required=False,
                        help='Log progress output in terminal.')
    
    args = parser.parse_args()


#get device info and search in CW, if exists uninstall CB
#'av_status': ['AV_DEREGISTERED']

    
