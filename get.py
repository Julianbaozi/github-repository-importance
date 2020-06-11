# ! !/usr/bin/env python3
# -*- coding: utf-8 -*-

import datetime
import pandas as pd

import query
import pre_select

from torrequest import TorRequest
import feature_getter
import sys
import traceback
import ray
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.proxy import Proxy, ProxyType
from conf import PW_TOR


def run(owner_repos):
    columns = ['name', 'size', 'stars', 'watches', 'forks', 'owner_type', 'if_fork',
               'commits', 'branches', 'releases', 'contributors', 'projects', 'labels', 'milestones',
               'open_issues', 'closed_issues', 'open_issues_recent', 'closed_issues_recent',
               'open_prs', 'closed_prs', 'open_prs_recent', 'closed_prs_recent',
               'age', 'recent_contributors', 'recent_commits', 'recent_added', 'recent_deleted',
               'dependent_repositories', 'dependent_packages', 'repositories', 'people', 'followers']

    df = pd.DataFrame(columns=columns)
    df.to_csv('result/data.csv', index=False)

    # ray.init(address='redis_address', redis_password=redis_password)
    ray.init()

    @ray.remote
    def process_repo(owner_repo):

        tr = TorRequest(password=PW_TOR)
        tr.reset_identity()
        response = tr.get("http://ipecho.net/plain")
        new_ip = response.text
        proxy = Proxy({
            'proxyType': ProxyType.MANUAL,
            'httpProxy': new_ip,
            'ftpProxy': new_ip,
            'sslProxy': new_ip,
            'noProxy': ''  # set this value as desired
        })
        print("New Ip Address", new_ip)
        browser = webdriver.Firefox(options=options, proxy=proxy)
        app_init0 = datetime.datetime.now()
        try:
            getter = feature_getter.FeatureGetter(owner_repo, browser, new_ip)
            getter.get_features()
            # print(getter.result)

            save_result_obj = query.save_result(result_path='result/', lock_path='lock/')
            save_result_obj.append_dict_as_row('data.csv', getter.result, columns)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            if hasattr(e, 'message'):
                print(e.message)
            else:
                print(e)
            print(owner_repo + ' not finished.')
        browser.close()

        app_init1 = datetime.datetime.now()
        total_time_min = (app_init1 - app_init0).total_seconds() / 60
        print("Finished " + owner_repo + " in %.2f min" % total_time_min)

    app_init = datetime.datetime.now()
    x = []
    options = Options()
    options.headless = True

    for i in range(len(owner_repos)):
        x.append(process_repo.remote(owner_repos[i]))
    ray.get(x)

    total_time_min = (datetime.datetime.now() - app_init).total_seconds() / 60
    print("Finished in %.2f min" % total_time_min)


if __name__ == '__main__':
    with open('owner_repos.txt') as file:
        owner_repos = file.read().splitlines()
    run(owner_repos=owner_repos[:])

