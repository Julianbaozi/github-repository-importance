# ! !/usr/bin/env python3
# -*- coding: utf-8 -*-

import datetime
import pandas as pd

from csv import DictWriter
from filelock import Timeout, FileLock

from torrequest import TorRequest
import feature_getter_
import sys
import traceback
import ray
import time
import random

from stem import Signal
from stem.control import Controller
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.proxy import Proxy, ProxyType
from bs4 import BeautifulSoup

from conf import IF_TOR, PW_TOR, IF_NEW

# signal TOR for a new connection
def switchIP():
    with Controller.from_port(port = 9051) as controller:
        controller.authenticate(PW_TOR)
        controller.signal(Signal.NEWNYM)

# get a new selenium webdriver with tor as the proxy
def my_proxy(PROXY_HOST,PROXY_PORT):
    fp = webdriver.FirefoxProfile()
    # Direct = 0, Manual = 1, PAC = 2, AUTODETECT = 4, SYSTEM = 5
    fp.set_preference("network.proxy.type", 1)
    fp.set_preference("network.proxy.socks",PROXY_HOST)
    fp.set_preference("network.proxy.socks_port",int(PROXY_PORT))
    fp.update_preferences()
    options = Options()
    options.headless = True
    #options.log.level = "trace"
    return webdriver.Firefox(options=options, firefox_profile=fp)

class save_result:
	def __init__(self, result_path, lock_path):
		self.result_path = result_path
		self.lock_path = lock_path

	def append_dict_as_row(self, file_name, dict_of_elem, field_names):
	    # Open file in append mode
		lock = FileLock(self.lock_path + file_name + ".lock")
		with lock:
		    with open(self.result_path +  file_name, 'a+', newline='') as write_obj:
		        # Create a writer object from csv module
		        dict_writer = DictWriter(write_obj, fieldnames=field_names)
		        # Add dictionary as wor in the csv
		        dict_writer.writerow(dict_of_elem)

	def append_line(self, file_name, line):
		lock = FileLock(self.lock_path + file_name + ".lock")
		with lock:
			with open(self.result_path + file_name, "a") as file:
				file.write(line + '\n')

def run(owner_repos):
    columns = ['full_name', 'mirror_url', 'archived', 'disabled'] + ['size', 'stars', 'watches', 'forks', 'owner_type', 'if_fork', 'description', 'homepage', 'license', 'files',
               'language', 'formats', 'commits', 'branches', 'releases', 'contributors', 'topics','age',
               'has_issues', 'open_issues', 'closed_issues', 'open_issues_recent', 'closed_issues_recent',
               'open_prs', 'closed_prs', 'open_prs_recent', 'closed_prs_recent', 'labels', 'milestones',
               'recent_contributors', 'recent_commits', 'recent_added', 'recent_deleted',
               'dependent_repositories', 'dependent_packages', 'repositories', 'people', 'followers', 'info', 'readme']

    if IF_NEW:
        df = pd.DataFrame(columns=columns)
        df.to_csv('result/data0_.csv', index=False)
        with open('result/failed.txt', 'w') as f:
            f.write('')

    # ray.init(address='redis_address', redis_password=redis_password)
    ray.init(webui_host='0.0.0.0')
    @ray.remote
    def process_repo(owner_repo, wait=0):
        save_result_obj = save_result(result_path='result/', lock_path='lock/')

        #print("Let's wait %d"% (wait))
        time.sleep(wait)
        #time.sleep(random.randint(0, 30))
        app_init0 = datetime.datetime.now()
        for _ in range(3):
            #if flag[0] == 0:
            #    time.sleep(random.randint(0, 30))

            try:
                switchIP()
                browser = my_proxy("127.0.0.1", 9050)
                browser.set_page_load_timeout(30)

                getter = feature_getter_.FeatureGetter(owner_repo, browser, '')
                getter()
                save_result_obj.append_dict_as_row('data0_.csv', getter.result, columns)
                try:
                    browser.close()
                except:
                    pass
                break
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
                if hasattr(e, 'message'):
                    print(e.message)
                else:
                    print(e)
                print(owner_repo + ' not finished. Retrying...')
                try:
                    browser.close()
                except:
                    pass
        else:
            print('Failed: ' + owner_repo)
            save_result_obj.append_line('failed.txt', owner_repo)

        app_init1 = datetime.datetime.now()
        total_time_min = (app_init1 - app_init0).total_seconds() / 60
        print("Finished " + owner_repo + " in %.2f min" % total_time_min)

    app_init = datetime.datetime.now()
    x = []
    for i in range(min(8, len(owner_repos))):
        x.append(process_repo.remote(owner_repos[i], 10 * i))
    for i in range(8, len(owner_repos)):
        x.append(process_repo.remote(owner_repos[i]))
    ray.get(x)

    total_time_min = (datetime.datetime.now() - app_init).total_seconds() / 60
    print("Finished in %.2f min" % total_time_min)

if __name__ == '__main__':
    with open('owner_repos.txt') as file:
        owner_repos = file.read().splitlines()
    #owner_repos = ['Nikesh001/android_kernel_xiaomi_msm8937']
    run(owner_repos[:])

