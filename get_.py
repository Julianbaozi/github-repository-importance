# ! !/usr/bin/env python3
# -*- coding: utf-8 -*-

import datetime
import pandas as pd

import query
import pre_select

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

def run(owner_repos):
    columns = ['name', 'size', 'stars', 'watches', 'forks', 'owner_type', 'if_fork',
               'commits', 'branches', 'releases', 'contributors', 'projects', 'labels', 'milestones',
               'open_issues', 'closed_issues', 'open_issues_recent', 'closed_issues_recent',
               'open_prs', 'closed_prs', 'open_prs_recent', 'closed_prs_recent',
               'age', 'recent_contributors', 'recent_commits', 'recent_added', 'recent_deleted',
               'dependent_repositories', 'dependent_packages', 'repositories', 'people', 'followers', 'info']

    if IF_NEW:
        df = pd.DataFrame(columns=columns)
        df.to_csv('result/data2.csv', index=False)
        with open('result/failed.txt', 'w') as f:
            f.write('')

    # ray.init(address='redis_address', redis_password=redis_password)
    ray.init()
    @ray.remote
    def process_repo(owner_repo):
        save_result_obj = query.save_result(result_path='result/', lock_path='lock/')
        for _ in range(3):
            time.sleep(random.randint(2, 40))
            app_init0 = datetime.datetime.now()

            switchIP()
            browser = my_proxy("127.0.0.1", 9050)
            try:
                getter = feature_getter_.FeatureGetter(owner_repo, browser, '')
                getter()
                # print(getter.result)
                if 'info' in getter.result and getter.result['info'] == "Not Found":
                    print("Not Found: " + owner_repo)
                save_result_obj.append_dict_as_row('data2.csv', getter.result, columns)
                browser.close()
                break
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
                if hasattr(e, 'message'):
                    print(e.message)
                else:
                    print(e)
                print(owner_repo + ' not finished. Retrying...')
                browser.close()
        else:
            print('Failed: ' + owner_repo)
            save_result_obj.append_line('failed.txt', owner_repo)

        app_init1 = datetime.datetime.now()
        total_time_min = (app_init1 - app_init0).total_seconds() / 60
        print("Finished " + owner_repo + " in %.2f min" % total_time_min)

    app_init = datetime.datetime.now()
    x = []
    
    for i in range(len(owner_repos)):
        x.append(process_repo.remote(owner_repos[i]))
    ray.get(x)

    total_time_min = (datetime.datetime.now() - app_init).total_seconds() / 60
    print("Finished in %.2f min" % total_time_min)
    print("Failed: ", failed)

if __name__ == '__main__':
    with open('failed.txt') as file:
        owner_repos = file.read().splitlines()
    run(owner_repos=owner_repos[:])

