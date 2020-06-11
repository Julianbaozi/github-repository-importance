import json
import os
import configparser

from conf import TOKEN, STUDIES

def replace_name(owner_repo):
	owner_repo = owner_repo.replace('/',';')
	return owner_repo

def set_project(owner_repo):
	new_project = \
	{
		owner_repo: {
		"git": [
			"https://github.com/" + owner_repo + ".git"
			],
	 		"github:repo": [
				"https://github.com/" + owner_repo
			],
			"github:issue": [
				"https://github.com/" + owner_repo
			]
		}
	 }

	
	with open('settings/projects/project_' + replace_name(owner_repo) + '.json', 'w+') as f:
		json.dump(new_project, f, indent=4)

def set_setup(owner_repo, start_date_str, api_token):
	
	configfile_name = 'settings/setup.cfg'
	config = configparser.ConfigParser(allow_no_value=True)
	
	new_owner_repo = replace_name(owner_repo)
	config.read_file( open(configfile_name)	)
	config["projects"]["projects_file"] = 'settings/projects/project_' + new_owner_repo + '.json'
	# config["git"]["raw_index"] = 'git:' + new_owner_repo + ':raw'
	# # config["git"]["enriched_index"] = 'git:' + new_owner_repo + ':enriched'
	# config["github:issue"]["raw_index"] = 'github-issue:' + new_owner_repo + ':raw'
	# config["github:issue"]["enriched_index"] = 'github-issue:' + new_owner_repo + ':enriched'
	# config["github:repo"]["raw_index"] = 'github-repo:' + new_owner_repo + ':raw'
	# config["github:repo"]["enriched_index"] = 'github-repo:' + new_owner_repo + ':enriched'
	# config["enrich_onion:git"]["in_index"] = config["git"]["enriched_index"]
	# config["enrich_onion:git"]["out_index"] = 'git-onion:' + new_owner_repo + ':enriched'
	# config["enrich_areas_of_code:git"]["in_index"] = config["git"]["raw_index"]
	# config["enrich_areas_of_code:git"]["out_index"] = 'git-aoc:' + new_owner_repo + ':enriched'
	

	config["github:issue"]["from-date"] = start_date_str

	#config["sortinghat"]["identities_api_token"] = api_token
	#config["github:issue"]["api-token"] = api_token
	#config["github:repo"]["api-token"] = api_token
	
	studies_list = [study for study in STUDIES if STUDIES[study]]
	config["git"]["studies"] = repr(studies_list)

	with open('settings/setups/setup_'+ new_owner_repo +'.cfg', "w") as configfile:
		config.write(configfile)

def set(owner_repo, start_date_str):
	set_project(owner_repo)
	set_setup(owner_repo, start_date_str, TOKEN)

