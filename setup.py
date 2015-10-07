#!/usr/bin/python
import subprocess
import json
import time
from DigitalOceanAPIv2.docean import DOcean
from ElasticPowerTAC_GoogleDrivePlugin.googledrive_upload_wrapper import GoogleDriveUpload
'''
	Setup PowerTAC Simulations
	* Creates a DigitalOcean droplet with specified Master image id
	* SCP Master configuration json
	* screen Run Master 
'''


class ElasticPowerTAC:
	# constructor
	def __init__(self):
		self._config = None

		# Load config
		self.load_config()

		# Create DOcean API Wrapper
		self._docean = DOcean(self._config['api-key'])

		# Use GoogleDrive Upload API
		self._google_drive_uploader = None
		self._google_drive_session = 'google-session.json'
		# Check if we are using it if so run setup session
		if self._config['google-drive']:
			self._setup_session()



	# load_config
	def load_config(self):
		# load from "config.json"
		try:
			config_file = "config.json"
			self._config = None
			with open(config_file,'r') as f:
				self._config = f.read()

			self._config = json.loads(self._config)
		except:
			print('config.json must be defined.')
			exit()

	# Google Drive API Session Setup
	def _setup_session(self):
		self._google_drive_uploader = GoogleDriveUpload(self._config['google-drive-secret'],
														self._google_drive_session)

	# Wait creation process
	def wait_until_completed(self,droplet_id):
		# poll until last action is completed.
		while True:
			actions = self._docean.request_droplet_actions(droplet_id)
			# Check all actions are complete
			actions_all_completed = True
			for action in actions['actions']:
				if action['status'] != 'completed':
					actions_all_completed = False
			if not actions_all_completed:
				# If not finished sleep for 1 minute
				time.sleep(60)
			else:
				break

	# setup master droplet
	def setup_master_droplet(self):

		# Create master with specified image id
		status,new_droplet = self._docean.request_create(
								self._config['master-name'],
								self._config['master-image']['region'],
								self._config['master-image']['size'],
								self._config['master-image']['id'],
								self._config['master-image']['ssh_keys'])
		
		# Check status
		if status != 202:
			print('Unable to create master droplet')
			exit()

		droplet_info = new_droplet['droplet']
		# wait for creation action to finish
		print('Initilized creation process of master')

		# Poll actions every minute until finished
		droplet_id = droplet_info['id']
		self.wait_until_completed(droplet_id)

		# Completed
		print('Finished creating Master Droplet(%d)'%droplet_id)
		self._master_droplet = droplet_id

	# setup master environment
	def setup_master_environment(self):
		# Retrieve IP Address of Master Droplet
		response = self._docean.request_droplets()
		for droplet in response['droplets']:
			if droplet['id'] == self._master_droplet:
				self._master_ip = droplet['networks']['v4'][0]['ip_address']
				break


		# Setup master_config dict
		master_config = {}
		master_config['local-ip'] = self._master_ip
		master_config['slave-name'] = "PTSlave-under-%s"%self._master_droplet
		master_config['slave-image'] = self._config['slave-image']
		master_config['api-key'] = self._config['api-key']
		master_config['slaves-used'] = self._config['slaves-used']
		master_config['simulations'] = self._config['simulations']
		if self._config['google-drive']:
			master_config['google-drive'] = self._config['google-drive']
			master_config['master-droplet-id'] = self._master_droplet
		else:
			master_config['google-drive'] = False

		master_config_file = 'master.config.json'

		# Create necessary config.json file for master
		with open(master_config_file,'w+') as f:
			f.write(json.dumps(master_config))


		# Attempt to ssh over
		completed = False
		while not completed:
			try:
				# Clone ElasticPowerTAC-Master
				cmd_clone = ['ssh','-o StrictHostKeyChecking=no',('root@%s'%self._master_ip),
				'git clone --recursive https://github.com/frankyn/ElasticPowerTAC-Master.git']
				subprocess.call(cmd_clone)

				# SCP master.config.json to master server
				cmd_mcj = ['scp',master_config_file,
						   'root@%s:%s'%(self._master_ip,'~/ElasticPowerTAC-Master/config.json')]
				subprocess.call(cmd_mcj)

				if self._config['google-drive']:
					# SCP session.json to master server
					cmd_cpgd = ['scp',self._google_drive_session,
							   'root@%s:%s'%(self._master_ip,'~/ElasticPowerTAC-Master/%s'%self._google_drive_session)]
					subprocess.call(cmd_cpgd)



				# Run ElasticPowerTAC-Master
				cmd_run = ['ssh','root@%s'%self._master_ip,
						   'cd ~/ElasticPowerTAC-Master/;python master.py  < /dev/null > /tmp/master-log 2>&1 &']
				subprocess.call(cmd_run)

				# We are finished
				completed = True
			except:
				print('Unable to SSH in.. wait another minutes')
				time.sleep(60)

		print("Master has been initialized")




if __name__ == "__main__":
	# Initialize Setup
	elastic_powertac = ElasticPowerTAC()
	
	# Setup Master Droplet
	elastic_powertac.setup_master_droplet()

	# Setup Master Environment
	elastic_powertac.setup_master_environment()

	# Setup Done.
	print("Finished setup.py")
