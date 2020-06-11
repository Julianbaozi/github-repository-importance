#! !/usr/bin/env python3

from pprint import pprint

from elasticsearch import Elasticsearch 
from elasticsearch_dsl import Search

import datetime
import dateutil.parser
from collections import defaultdict

import set_params

import argparse
import sys
import os
import csv
from csv import DictWriter
import json
from filelock import Timeout, FileLock

from conf import *


def milisec2iso(milliseconds):
	time0 = dateutil.parser.isoparse('1970-01-01T00:00:00')
	delta = datetime.timedelta(milliseconds=milliseconds)
	return time0 + delta

def iso2milisec(iso):
	delta = dateutil.parser.isoparse(iso) - dateutil.parser.isoparse('1970-01-01T00:00:00')
	delta = delta.total_seconds() * 1000
	return delta

def query(es, owner_repo, start_date_str):
	
	git = BACKENDS['git']
	github_issue = BACKENDS['github:issue']
	github_repo = BACKENDS['github:repo']

	git_aoc = STUDIES['enrich_onion:git']
	git_onion = STUDIES['enrich_onion:git']

	new_owner_repo = set_params.replace_name(owner_repo)
	results = {'owner_repo':owner_repo}
	pop_list = []
	domain_author_count = {}
	queries = []

	if git:
		def S_git():
			s = Search(using=es, index='git_enriched')
			s = s.update_from_dict({'query':{'bool': {'must':[
												{'term' : {'Author_bot' : 'false'}},
												{'term' : {'Commit_bot' : 'false'}},
												{'term' : {'github_repo' : owner_repo}}]}}})
			return s

		def S_git_recent():
			s = S_git()
			s = s.query('range', **{'grimoire_creation_date':{'gt':start_date_str}})
			return s

		queries.append((S_git(), 'first_commit_date', 'min', 'commit_date'))
		queries.append((S_git(), 'last_commit_date', 'max', 'commit_date'))
		queries.append((S_git(), 'num_added', 'sum', 'lines_added'))
		queries.append((S_git(), 'num_removed', 'sum', 'lines_removed'))
		queries.append((S_git_recent(), 'num_authors', 'cardinality', 'author_uuid'))
		queries.append((S_git_recent(), 'num_committers', 'cardinality', 'Commit_uuid'))
		queries.append((S_git_recent(), 'num_domains', 'cardinality', 'Author_domain'))
		queries.append((S_git_recent(), 'time_to_commit_hours', 'avg', 'time_to_commit_hours'))
		queries.append((S_git_recent(), 'num_changed', 'sum', 'lines_changed'))

		s = S_git_recent()
		results['num_commits'] = s.count()


		#s = S_git()
		#s = s.query('bool', **{'must_not':{'term':{'author_domain': 'Unknown'}}})
		#s.aggs.bucket('num_authors_of_domain', 'terms', field = 'author_domain').metric('domain_author_count', 'cardinality', field = 'author_uuid')
		#s = s.execute()
		#buckets = s.aggregations.num_authors_of_domain.buckets
		#domain_author_count = {}
		#for domain in buckets:
		#	domain_author_count[domain['key']] = domain['domain_author_count']['value']

	if git_aoc:
		def S_aoc():
			s = Search(using=es, index='git-aoc_enriched')
			s = s.query('term', **{'project' : owner_repo})
			return s

		s = S_aoc()
		s1 = s.query('term', **{'fileaction':'FILE_A'})
		num_added_files = s1.count()
		s2 = s.query('term', **{'fileaction':'FILE_D'})
		num_deleted_files = s2.count()
		results['num_files'] = num_added_files - num_deleted_files

	if git_onion:
		def S_git_onion():
			s = Search(using=es, index='git-onion_enriched')
			s = s.query('term', **{'project' : owner_repo})
			return s

		s = S_git_onion()
		s.aggs.metric('num_quater', 'cardinality', field = 'grimoire_creation_date')
		s = s.execute()
		num_quater = s.aggregations.num_quater.value

		if num_quater == 0:
			num_core = num_regular = num_casual = 0
		else:
			s = S_git_onion()
			s1 = s.query('term', **{'onion_role':'core'})
			num_core = s1.count() / num_quater


			s = S_git_onion()
			s2 = s.query('term', **{'onion_role':'regular'})
			num_regular = s2.count() / num_quater


			s = S_git_onion()
			s3 = s.query('term', **{'onion_role':'casual'})
			num_casual = s3.count() / num_quater

		results['num_core'], results['num_regular'], results['num_casual'] = num_core, num_regular, num_casual

	# github-issue
	if github_issue:
		def S_github():
			s = Search(using=es, index='github-issue_enriched')
			s = s.update_from_dict({'query':{'bool': {'must':[
											{'term' : {'author_bot' : 'false'}},
											{'term' : {'assignee_data_bot' : 'false'}},
											{'term' : {'github_repo' : owner_repo}}]}}})
			return s

		queries.append((S_github(), 'time_to_first_attention', 'avg', 'time_to_first_attention'))
		queries.append((S_github(), 'num_issue_authors', 'cardinality', 'author_uuid'))
		queries.append((S_github(), 'num_issue_domains', 'cardinality', 'author_domain'))

		def S_item_state(state, item_type):
			s = S_github()
			s = s.query('term', **{'state':state})
			s = s.query('term', **{'item_type': item_type})
			return s

		field = {'closed': 'time_to_close_days', 'open': 'time_open_days'}
		num_item_state = defaultdict(lambda:{})
		time_item_state = defaultdict(lambda:{})
		
		transfer = {'issue':'issue', 'pull request':'pr'}
		for state in ['closed', 'open']:
			for item_type in ['issue', 'pull request']:
				s = S_item_state(state, item_type)
				results['num_'+state+'_'+transfer[item_type]] = s.count()
				s.aggs.metric(field[state], 'avg', field = field[state])
				s = s.execute()
				results['time_'+state+'_'+transfer[item_type]] = s.aggregations[field[state]].value
		
		for item_type in ['issue', 'pull request']:
			for field_name in ['created_at', 'updated_at']:
				queries.append((S_github().query('term', **{'item_type': item_type}), 'last_'+field_name[:8]+transfer[item_type]+'_date', 'max', field_name))

	#github-repo
	if github_repo:
		s = Search(using=es, index='github-repo_raw')
		s = s.query('term', **{'data.full_name':owner_repo})
		s = s.execute()
		s = s[-1]['data']
		results['size'] = s['size']
		results['num_stars'] = s['stargazers_count']
		results['num_forks'] = s['forks_count']
		results['num_subscribers'] = s['subscribers_count']
		results['num_total_open_issues'] = s['open_issues_count']
		results['num_repos'] = s['owner_repos_count'] 
		results['num_followers'] = s['followers_count']


	for source, name, function_name, field_name in queries:
#		print(source, name, function_name, field_name)
		s = source
		s.aggs.metric(name, function_name, field=field_name)
		s = s.execute()
		results[name] = s.aggregations[name].value

	if git:
		results['age'] = datetime.datetime.now().timestamp()*1000 - results['first_commit_date']
		results['num_lines'] = results['num_added']- results['num_removed']
	

	if IF_PRINT:
		print(results)
#		print('Age: ', datetime.timedelta(milliseconds=results['age']).days, 'days')
#		print("Number of lines: ", results['num_lines'])
#		print('Date of the first commit:', milisec2iso(results['first_commit_date']) if results['first_commit_date'] is not None else None)
#		print('Date of the latest commit:', milisec2iso(results['last_commit_date']) if results['last_commit_date'] is not None else None)
#		print("Number of commits: ", results['num_commits'])
#		print("Number of unique authors: ", results['num_authors'])
#		print("Number of unique committers: ", results['num_committers'])
#		print("Number of unique author domains: ", results['num_domains'])
#		print("Time to commit hours : ", results['time_to_commit_hours'])
#		print("Number of changed lines: ", results['num_changed'])
#		print("Number of files: ", results['num_files'])
#		print('Number of core member each quater: ', results['num_core'])
#		print('Number of regular member each quater: ', results['num_regular'])
#		print('Number of casual results member each quater: ', results['num_casual'])
#		print('Size of Github: ', results['size'])
#		print('Number of stars: ', results['num_stars'])
#		print('Number of forks: ', results['num_forks'])
#		print('Number of subscribers: ', results['num_subscribers'])
#		print('Number of total open issues: ', results['num_total_open_issues'])
#		print("Time to first attention: ", results['time_to_first_attention'])
#		print("Number of unique issue authors: ", results['num_issue_authors'])
#		print("Number of unique issue author domains: ", results['num_issue_domains'])
#		print('Date of he latest pull request:', milisec2iso(results['last_created_pr_date']) if results['last_created_pr_date'] is not None else None)
#		print('Date of the latest issue:', milisec2iso(results['last_created_issue_date']) if results['last_created_issue_date'] is not None else None)
#		print('Number of closed issue: ', results['num_closed_issue'] )
#		print('Time of open days for issue: ', results['time_open_issue'] )


	pop_list=['num_added', 'num_removed', 'first_commit_date']
	for name in pop_list:
		if name in results:  
		    results.pop(name)

	return results#, domain_author_count

def get_params_parser():
    """Parse command line arguments"""

    parser = argparse.ArgumentParser(add_help=False)

    parser.add_argument('-e', '--es_paths',  dest='es_paths', nargs='*', required=True,
                        help='es')
    parser.add_argument('-o', '--owner_repo',  dest='owner_repo', required=True,
                        help='owner_repo')
    parser.add_argument('-s', '--start_date_str',  dest='start_date_str', default='1970-01-01T00:00:00',
                        help='start_date_str')
    parser.add_argument('-c', '--columns',  dest='columns', nargs='*', required=True,
                        help='columns')
    parser.add_argument('-i', '--IF_PRINT',  dest='IF_PRINT', default=False,
                        help='IF_PRINT')

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    return parser


def get_params():
    """Get params to execute query"""

    parser = get_params_parser()
    args = parser.parse_args()
    return args

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

	def append_dict_to_json(self, file_name, dict_of_elem):
		lock = FileLock(self.lock_path + file_name + ".lock")
		with lock:
			with open(self.result_path + file_name, "r+") as file:
				json_data = json.load(file)
				json_data.update(dict_of_elem)
				file.seek(0)
				json.dump(json_data, file, indent=4)

	def append_line(self, file_name, line):
		lock = FileLock(self.lock_path + file_name + ".lock")
		with lock:
			with open(self.result_path + file_name, "a") as file:
				file.write(line + '\n')


def remove_settings(es, new_owner_repo):
	# es.indices.delete(index='git_raw', ignore=[400, 404])
	# es.indices.delete(index='github-issue_raw', ignore=[400, 404])
	# es.indices.delete(index='github-repo_enriched', ignore=[400, 404])
	os.remove('settings/projects/project_' + new_owner_repo + '.json')
	os.remove('settings/setups/setup_'+ new_owner_repo +'.cfg')

def run(owner_repo, start_date_str, columns):
	es = Elasticsearch(ES_PATHS)

	data = query(es, owner_repo, start_date_str)

	save_result_obj = save_result(result_path = 'result/', lock_path = 'lock/')
	save_result_obj.append_dict_as_row('data.csv', data, columns)
	#save_result_obj.append_dict_to_json('domain_author_count.json', {owner_repo : domain_author_count})

	new_owner_repo = set_params.replace_name(owner_repo)
	remove_settings(es, new_owner_repo)

if __name__ == '__main__':
	args = get_params()
	es = Elasticsearch(args.es_paths)
	
	new_owner_repo = set_params.replace_name(args.owner_repo)
	
	data, domain_author_count = query(es, args.owner_repo, args.start_date_str, args.IF_PRINT)

	append_dict_as_row('result/data.csv', data, args.columns)
	append_dict_to_json('result/domain_author_count.json', {args.owner_repo : domain_author_count})

	new_owner_repo = set_params.replace_name(args.owner_repo)
	remove_settings(new_owner_repo)

#	IF_PRINT = True
#	for repo in ['git-up/GitUp']:
#    		query(Elasticsearch(ES_PATHS), repo,'2020-01-01')

# print(query('chaoss/grimoirelab','2020-03-30',True).keys())
# a = "size, age, num_lines, num_files, num_stars, num_forks, num_subscribers, num_total_open_issues, num_core, num_regular, num_casual, \
# 	num_commits, num_authors, num_committers, num_domains, num_changed, num_closed_issue, num_closed_pr, num_open_issue, num_open_pr, \
# 	last_commit_date, last_pr_date, last_issue_date, time_to_commit_hours, time_to_first_attention, time_to_close_days_issue, time_to_close_days_pr, time_open_days_issue, time_open_days_pr"
# a = a.replace('\t', '')
# # b = a.replace("['issue']", "_issue").replace("['pull request']", "_pr")
# b = a.split(', ')
# print(b)\
