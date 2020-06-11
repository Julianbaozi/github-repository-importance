#! !/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess

import datetime 

import json

import init
import patcher

import set_params
import micro
import query
import pre_select

import ray
from conf import *

def run(owner_repos):

	columns = init.init()
	patcher.patch()

	# ray.init(address='redis_address', redis_password=redis_password)
	ray.init()

	@ray.remote
	def process_repo(owner_repo):
		try:
			start_date = datetime.datetime.now() - datetime.timedelta(days=TIME_DELTA)
			start_date_str = start_date.strftime("%Y-%m-%d")
	
			app_init0 = datetime.datetime.now()
			print('\nPROCESSING ' + owner_repo + '.')
			set_params.set(owner_repo, start_date_str)
	
			cfg_path = 'settings/setups/setup_' + set_params.replace_name(owner_repo) + '.cfg'
			if_pass = True
			if BACKENDS['github:repo']:
				micro.micro_mordred(cfg_path, ['github:repo'], raw=True, enrich=False)
				if_pass = pre_select.pre_select()
			if if_pass:
				backends = [backend for backend in BACKENDS if BACKENDS[backend] and backend!='github:repo']
				micro.micro_mordred(cfg_path, backends, raw=True, enrich=True)
	
			query.run(owner_repo, start_date_str, columns)
			app_init1 = datetime.datetime.now()
			total_time_min = (app_init1 - app_init0).total_seconds() / 60	
			print("Finished " + owner_repo + " in %.2f min" % (total_time_min))
		except:
			print("Failure on " + owner_repo + "!" )
			err.append(owner_repo)

	app_init = datetime.datetime.now()
	x = []
	err = []
	for i in range(len(owner_repos)):
		x.append(process_repo.remote(owner_repos[i]))
	ray.get(x)


	total_time_min = (datetime.datetime.now() - app_init).total_seconds() / 60
	print("Finished in %.2f min" % (total_time_min))

if __name__ == '__main__':
	with open('owner_repos.txt') as file:
		owner_repos = file.read().splitlines()
		
	run(owner_repos=owner_repos[:])

