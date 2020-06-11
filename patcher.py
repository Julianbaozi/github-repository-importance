import importlib
import sys
import json

from conf import *

class source_patch:
	"""Patch the source code to meet our needs
	
	:param: path: path of the source code
	"""
	
	def __init__(self, path):
		self.path = path
		with open(path, 'r') as f:
			self.source = f.read()

	def _save(self):
		"""Save source code to path"""
		with open(self.path, 'w') as f:
			f.write(self.source)

	def _replace(self, str_to_delete='', str_to_insert='', pre_str=None, post_str=None, pre_ind=None, post_ind=None):
		"""Replace a string in source.
		When pre_str==pre_ind==None, then pre_ind is the end of  the source.
		When post_str==post_ind==None, then post_ind is the end of  the source.
			
		:param: str_to_delete: the string to be deleted
		:param: str_to_insert: the string to be inserted
		:param: pre_str: the string before what you want to replace
		:param: post_str: the string after what you want to replace
		:param: pre_ind: string head index
		:param: post_ind: string end index + 1
		"""

		if str_to_delete:
			pos = self.source.find(str_to_delete)
			if pos == -1:
				print("Can't find str_to_delete. Source not replaced.")
				return
			self.source = self.source.replace(str_to_delete, str_to_insert)
		else:
			if pre_str is not None:
				pos = self.source.find(pre_str)
				if pos == -1:
					print("Can't find pre_str. Source not replaced.")
					return
				pre_ind = pos + len(pre_str)
			elif pre_ind is None:
				pre_ind = len(self.source)

			if post_str is not None:
				pos = self.source[pre_ind:].find(post_str)
				if pos == -1:
					print("Can't find post_str. Source not replaced.")
					return
				post_ind = pre_ind + pos
			elif post_ind is None:
				post_ind = len(self.source)
			
			self.source = self.source[:pre_ind] + str_to_insert + self.source[post_ind:]

	def _insert(self, str_to_insert='', pre_str=None, pre_ind=None):
		"""Insert a string in source.
		When pre_str==pre_ind==None, then pre_ind is the end of  the source.
			
		:param: str_to_insert: the string to be inserted
		:param: pre_str: the string before what you want to insert
		:param: pre_ind: string head index
		"""
		self._replace(str_to_insert=str_to_insert, pre_str=pre_str, post_str='', pre_ind=pre_ind)

	def _delete(self, str_to_delete='', pre_str=None, post_str=None, pre_ind=None, post_ind=None):
		"""Replace a string in source.
		When pre_str==pre_ind==None, then pre_ind is the end of  the source.
		When post_str==post_ind==None, then post_ind is the end of  the source.
			
		:param: str_to_delete: the string to be deleted
		:param: pre_str: the string before what you want to delete
		:param: post_str: the string after what you want to delete
		:param: pre_ind: string head index
		:param: post_ind: string end index + 1
		"""
		self._replace(str_to_delete=str_to_delete, pre_str=pre_str, post_str=post_str, pre_ind=pre_ind, post_ind=post_ind)

class client_patch(source_patch):
	"""Add tor into client.py to make endless IPs

	:param: path: path to the module
	:param: if_tor: whether to use tor
	:param: pw_tor: password for tor
	:param: s: the string to be changed
	:param: pre_str: the string before what you want to change
	"""

	# def __init__(self, module_name, package, if_tor):
	# 	super().__init__(module_name, package)
	def __init__(self, path):
		super().__init__(path)
	
	def patch(self):
		"""Patch client and save to file"""
		s = \
	'        from torrequest import TorRequest\n' +\
	'        tr = TorRequest(password="' + PW_TOR + '")\n' +\
	'        tr.reset_identity()\n' +\
	'        response = tr.get("http://ipecho.net/plain")\n' +\
	'        new_ip = response.text\n' +\
	'        print("New Ip Address", new_ip)\n' +\
	'        self.session.proxies = {"http": "http://" + new_ip}\n'

		pre_str = "self.session = requests.Session()\n"

		if IF_TOR:
			if self.source.find(s) == -1:
				#insert patch
				super()._insert(str_to_insert=s, pre_str=pre_str)
		else:
			#delete patch
			super()._delete(str_to_delete=s)

		super()._save()

class index_lock_patch(source_patch):
	"""
        
        """
	def __init__(self, path):
		super().__init__(path)

	def patch(self):
		""""""
		s = \
'        from filelock import FileLock\n\
        lock_path = "lock/create_index.lock"\n\
        lock = FileLock(lock_path)\n\
        with lock:\n    '

		pre_str = \
'self.requests = grimoire_con(insecure)\n\
\n'
		if IF_INDEX_LOCK:
			if self.source.find(s) == -1:
				#insert patch
				super()._insert(str_to_insert=s, pre_str=pre_str)
		else:
			#delete patch
			super()._delete(str_to_delete=s)

		super()._save()

class github_patch(source_patch):
	""""""
	def __init__(self, path):
		super().__init__(path)

	def patch(self):
		""""""
		str_to_insert = "[] #['user', 'assignee', 'assignees', 'comments', 'reactions']"
		str_to_delete = "['user', 'assignee', 'assignees', 'comments', 'reactions']"
		if self.source.find(str_to_insert) == -1:
			self._replace(str_to_delete=str_to_delete, str_to_insert=str_to_insert)

		str_to_insert = \
'        repo["owner_repos_count"] = self.__get_owner_repos_count(repo["owner"]["repos_url"])\n\
        repo["followers_count"] = self.__get_followers_count(repo["owner"]["followers_url"])\n\
        yield repo\n\
\n\
    def __get_followers_count(self, followers_url):\n\
        """Get followers count"""\n\
        r = self.client.fetch(followers_url)\n\
        followers = r.text\n\
        followers = json.loads(followers)\n\
        return len(followers)\n\
\n\
    def __get_owner_repos_count(self, repos_url):\n\
        """Get repo count of the owner"""\n\
        r = self.client.fetch(repos_url)\n\
        repos = r.text\n\
        repos = json.loads(repos)\n\
        return len(repos)\n'
		str_to_delete = '        yield repo'
		if self.source.find(str_to_insert) == -1:
			self._replace(str_to_delete=str_to_delete, str_to_insert=str_to_insert)

		self._save()

# class lock_patch(source_patch):
# 	""""""
	
# 	def __init__(self, path):
# 		super().__init__(path)
# 		self.lock_path = '"lock/"'
# 		self.if_lock = True

	
# 	def _generate_patch(self, custom_lock_path, indent=False):
# 		""""""
# 		if not indent:
# 			s = \
# 	'        from filelock import FileLock\n' +\
# 			custom_lock_path +\
# 	'        lock = FileLock(lock_path)\n' +\
# 	'        with lock:\n'
# 		else:
# 			s = \
# 	'            from filelock import FileLock\n' +\
# 			custom_lock_path +\
# 	'            lock = FileLock(lock_path)\n' +\
# 	'            with lock:\n'

# 		return s

	
# 	def _patch(self, s ,pre_str, post_str):
# 		""""""
# 		if self.if_lock:
# 			if self.source.find(s) == -1:
# 				#insert patch
# 				super()._replace(str_to_insert='\n    ', str_to_delete='\n', pre_str=pre_str, post_str=post_str)
# 				super()._insert(str_to_insert=s, pre_str=pre_str)
# 		else:
# 			#delete patch
# 			super()._delete(str_to_delete=s)
# 			super()._replace(str_to_delete='\n    ', str_to_insert='\n', pre_str=pre_str, post_str=post_str)

# class lock_raw(lock_patch):
# 	""""""
# 	def __init__(self, raw_path):
# 		super().__init__(raw_path)

# 	def patch(self):
# 		lock_name = ' + json_items[0]["backend_name"].lower() + "-" + json_items[0]["category"] + '

# 		custom_lock_path = '        lock_path = ' + self.lock_path + lock_name + '"_raw.lock"\n'
# 		s = super()._generate_patch(custom_lock_path)

# 		pre_str = 'field_id = self.get_field_unique_id()\n'
# 		post_str = '\n        if len(json_items) != inserted:'

# 		super()._patch(s ,pre_str, post_str)
# 		super()._save()

# class lock_enriched(lock_patch):
# 	""""""
# 	def __init__(self, enriched_path, backend_name):
# 		super().__init__(enriched_path)
# 		self.backend_name = backend_name

# 	def patch(self):
# 		""""""
# 		if self.backend_name == 'git':
# 			lock_name = '"git"'
# 			custom_lock_path = '        lock_path = ' + self.lock_path + ' + "git_enriched.lock"\n'
# 			post_str = '\ndef enrich_demography'
# 			s = super()._generate_patch(custom_lock_path, True)
# 		else:
# 			custom_lock_path = \
# '        if bulk_json.find("forks_count")==-1:\n' +\
# '            lock_path = '  + self.lock_path + ' + "github-issue_enriched.lock"\n' +\
# '        else:\n' +\
# '            lock_path = '  + self.lock_path + ' + "github-repo_enriched.lock"\n'
			
# 			post_str = '\ndef add_repository_labels(self, eitem):'

# 			s = super()._generate_patch(custom_lock_path)
# 		pre_str = '        url = self.elastic.get_bulk_url()\n'

# 		super()._patch(s ,pre_str, post_str)
# 		super()._save()


def patch():
	"""Run all the patchs"""
	CLIENT_PATH = VENV_PATH + 'src/grimoirelab-perceval/perceval/client.py'
	client_patch(CLIENT_PATH).patch()
	
	INDEX_LOCK_PATH = VENV_PATH + 'src/grimoirelab-elk/grimoire_elk/elastic.py'
	index_lock_patch(INDEX_LOCK_PATH).patch()
	
	GITHUB_PATH = VENV_PATH + 'src/grimoirelab-perceval/perceval/backends/core/github.py'
	github_patch(GITHUB_PATH).patch()

if __name__ == '__main__':
	# with open('conf.json', 'r') as file:
	# 	conf = json.load(file)

	# conf = {'client_path':'patches/client/new_client.py', 'if_tor':True, 'pw_tor':'abcd'}
	patch()
