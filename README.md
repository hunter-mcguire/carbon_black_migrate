# carbon_black_migrate

This experimental project leverages the Carbon Black Live Response API to install the Cloud One Workload Security agent and also uninstall the Carbon Black sensor.

## The workflow is broken up into two python scripts:

- trend_install.py: This accepts Carbon Black device ids and attempts to install the trend agent with a deployment sceipt uploaded to the FIle Response API.
- cb_uninstall.py: Once the install script has completed the cb_uninstall.py script can be used uninstall the CB sensor. It leverages the agent_deployment.csv that gets created in install script to only uninstall device that have the trend agent installed.


### Prerequisites to running:
- install python
- python3 -m pip install -r requirements.txt
- need agent_deployment.csv in order to run cb_uninstall.py
- agent_deployment.csv will get created each run
