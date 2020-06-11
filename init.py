'''
schema
-------------------
overall features 
-------------------
size: size of the github repository
age: age of the repository in days
num_lines: 					total number of lines
num_files: 					number of files
num_stars: 					number of stars
num_forks: 					number of forks
num_subscribers: 			number of subscribers
num_total_open_issues:	 	number of open issues in total
num_core: 					average number of core members by quater
num_regular: 				average number of regular members by quater
num_casual: 				average number of casual members by quater
-------------------
recent fearures : only related to activities after the given date
-------------------
num_commits: 				number of commits
num_authors: 				number of authors
num_issue_authors: 			number of issue authors
num_committers: 			number of committers
num_domains: 				number of domains
num_issue_domains: 			number of issue domains
num_changed: 				number of lines changed
num_closed_issue: 			number of closed issues
num_closed pr: 				number of pull requests
num_open issue: 			number of open issues
num_open_pr: 				number of open pull requests

last_commit_date: 			date of the last commit
last_created_pr_date: 		date of the last pull request creation
last_created_issue_date: 	date of the last issue creation
last_updated_pr_date: 		date of the last pull request update
last_updated_issue_date: 	date of the last issue update
time_to_commit_hours: 		average hours from author date (when commit was originally created) to commit date (when the commit was made to the repository).
time_to_first_attention: 	average days of first attention to an issue or a pull request
time_closed_issue: 			average days to close an issue
time_closed_pr: 			average days to close a pull request
time_open_issue: 			average open days of new issues
time_open_pr: 				average open days of new pull requests

domain_author_count: 		for a repository, the numbers of people in different domains
domain_scale: 				the number of people in a domain

'''

import sys
import os
import glob
import shutil
import json
from elasticsearch import Elasticsearch
import pandas as pd

from conf import ES_PATHS, IF_NEW, BACKENDS, STUDIES

def init():
	columns = ['owner_repo']
	if BACKENDS['github:repo']:
		columns.extend(['size', 'num_stars', 'num_forks', 'num_subscribers', 'num_total_open_issues', 'num_repos', 'num_followers'])
	if BACKENDS['git']:
		columns.extend(['last_commit_date', 'num_authors', 'num_committers', 'num_domains', 'time_to_commit_hours', 'num_changed', 'age', 'num_lines', 'num_commits'])
	if BACKENDS['git'] and STUDIES['enrich_onion:git']:
		columns.extend(['num_files'])
	if BACKENDS['git'] and STUDIES['enrich_areas_of_code:git']:
		columns.extend(['num_core', 'num_regular', 'num_casual'])
	if BACKENDS['github:issue']:
		columns.extend(['num_issue_authors', 'num_issue_domains', 'time_to_first_attention', 'last_created_issue_date', 'last_updated_issue_date', 'last_created_pr_date', 'last_updated_pr_date',
		 'num_closed_issue', 'time_closed_issue', 'num_closed_pr', 'time_closed_pr', 'num_open_issue', 'time_open_issue', 'num_open_pr', 'time_open_pr'])

	print('There are', len(columns), 'columns.')
	
	files = glob.glob('settings/setups/*')
	for f in files:
		os.remove(f)
	
	files = glob.glob('settings/projects/*')
	for f in files:
		os.remove(f)

	es = Elasticsearch(ES_PATHS)
	es.indices.delete(index='*', ignore = [400, 404])

	if IF_NEW:
		df = pd.DataFrame(columns=columns)
		df.to_csv('result/data.csv', index=False)
		with open('result/domain_author_count.json', 'w') as file:
			json.dump({}, file)
	return columns
