import time

import requests
from bs4 import BeautifulSoup
import re

import datetime
from dateutil.parser import parse
import urllib.parse


from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import json
from conf import TIME_DELTA


def get_numbers(text):
    nums = re.findall('[0-9,]+', text)
    return [int(num.replace(',', '')) for num in nums]


class text_has_numbers(object):
    def __init__(self, locator, indices):
        self.locator = locator
        self.indices = indices

    def __call__(self, driver):
        elements = driver.find_elements(*self.locator)
        if len(elements) == 0:
            return False
        for i in self.indices:
            if not get_numbers(elements[i].text):
                return False
        return elements


class text_is_different:
    def __init__(self, locator, text):
        self.locator = locator
        self.text = text

    def __call__(self, driver):
        elements = driver.find_elements(*self.locator)
        if len(elements) == 0:
            return False
        actual_text = elements[0].text
        return elements if actual_text != self.text else False


class has_text(object):
    def __init__(self, locator, text):
        self.locator = locator
        self.text = text

    def __call__(self, driver):
        elements = driver.find_elements(*self.locator)
        if len(elements) == 0:
            return False
        result = []
        for element in elements:
            if self.text in element.text:
                result.append(get_numbers(element.text)[0])
        return result


class FeatureGetter:
    """Get features for a repository.

    :param: owner_repo: name of the repo
    """
    BASE_URL = 'https://github.com/'
    BASE_API_URL = 'https://api.github.com/repos/'

    def __init__(self, owner_repo, browser, proxy):
        self.owner_repo = owner_repo
        self.start_date = (datetime.datetime.now() - datetime.timedelta(days=TIME_DELTA)).isoformat()[:10]
        self.browser = browser
        self.proxies = {"http": "http://" + proxy}
        self.result = {'full_name': owner_repo}

    def __call__(self):
        self.get_features()

    @staticmethod
    def _get_item(soup_list, index, content_index=0):
        return int(re.findall('[0-9,]+', soup_list[index].contents[content_index])[0].replace(',', ''))

    @staticmethod
    def _get_complex_item(soup_list, index, content_index=0):
        return int(re.findall('[0-9,]+', soup_list[index].contents[content_index].contents[0])[0].replace(',', ''))

    def _get_elements(self, conditions, by, target, custom=None, wait=10):
        elements = []
        for i in range(2):
                try:
                        elements = WebDriverWait(self.browser, wait).until(
                                conditions((by, target)) if not custom else conditions((by, target), custom)
                            )
                        break
                except:
                    #print('Loading timeout. URL: ' + self.browser.current_url, '. Tried ' + str(i + 1) + ' times.')
                    pass
        return elements

    def _get_page_by_browser(self, endpoint):
        url = self.BASE_URL + self.owner_repo + endpoint
        self.browser.get(url)

    def _update_result(self, elements, indices, feature_names):
        for i in range(len(indices)):
            self.result[feature_names[i]] = get_numbers(elements[indices[i]].text)[0]

    def _get_page(self, endpoint):
        url = self.BASE_URL + self.owner_repo + endpoint

        page = requests.get(url, proxies=self.proxies)
        soup = BeautifulSoup(page.content, 'html.parser')
        return soup

    @staticmethod
    def _get_element_from_page(soup, tag, class_name):
        find_tag = soup.find_all(tag, class_=class_name)
        soup_list = list(find_tag)
        return soup_list

    def _get_code(self):
        endpoint = ''
        try:
            self._get_page_by_browser(endpoint)
        except:
            pass

        self._get_summary()
        if 'info' in self.result and self.result['info'] == 'Empty':
            return

        self._get_topics()
        age_link = self._get_age_link()
        #self.readme_name = self._get_readme_name()
        if age_link:
            self._get_age(age_link)
        #self._get_latest_commits()
        #if self.readme_name:
        #    self._get_readme(readme_name)
        if self.result['contributors'] == 0:
            self._get_contributors()

    def _get_latest_commits(self):
        endpoint = '/commits/' + self.default_branch
        self._get_page_by_browser(endpoint)
        conditions = EC.presence_of_all_elements_located
        by = By.CSS_SELECTOR
        target = 'div.commit-group-title'

        elements = self._get_elements(conditions, by, target)
        latest_commits = []
        for i in range(min(10, len(elements))):
            element = elements[i]
            commit_date = element.text[11:]
            latest_commits.append(self.age(commit_date))
        self.result['latest_commits'] = latest_commits

    def _get_contributors(self):
       # endpoint = '/graphs/contributors'
       # conditions = text_is_different
       # by = By.TAG_NAME
       # target = 'h2'
       # custom = 'Loading contributions…'

       # self._get_page_by_browser(endpoint)
       # self._get_elements(conditions, by, target, custom)

       # soup = BeautifulSoup(self.browser.page_source, 'html.parser')
       # find_tag = soup.find_all('span', class_='cmeta')
       # soup_list = list(find_tag)

       # commits = []
       # added = []
       # deleted = []
       # for i in range(len(soup_list)):
       #      num_commits = self._get_complex_item(soup_list, i, 0)
       #      num_added = self._get_complex_item(soup_list, i, 2)
       #      num_deleted = self._get_complex_item(soup_list, i, 4)
       #      if num_commits == 0:
       #          break
       #      commits.append(num_commits)
       #      added.append(num_added)
       #      deleted.append(num_deleted)
        url = self.BASE_API_URL + self.owner_repo + '/stats/contributors'

        self.browser.get(url)
        soup = BeautifulSoup(self.browser.page_source, "html.parser")
        page = json.loads(soup.find("body").text)
        self.result['contributors'] = len(page)


    def _get_summary(self):
        conditions = text_has_numbers
        by = By.CSS_SELECTOR
        target = 'span.d-none>strong'
        custom = [0]
        feature_names = ['commits']
       
        elements = self._get_elements(conditions, by, target, custom)
        if not elements and self.browser.page_source.find('This repository is empty.') != -1:
            self.result['info'] = 'Empty'
            return
        self._update_result(elements, custom, feature_names)

        target = 'div.flex-self-center>a>strong'
        custom = [0, 1]
        feature_names = ['branches', 'releases']
        elements = self._get_elements(conditions, by, target, custom)
        self._update_result(elements, custom, feature_names)
        
        conditions = has_text
        target = 'div.BorderGrid-row h2 a'
        custom = 'Contributors'
        feature_names = ['contributors']

        elements = self._get_elements(conditions, by, target, custom)
        if not elements:
            self.result['contributors'] = 0
            return
        self.result['contributors'] = elements[0]


    def _get_topics(self):
        conditions = EC.presence_of_all_elements_located
        by = By.CSS_SELECTOR
        target = 'a.topic-tag.topic-tag-link'

        elements = self._get_elements(conditions, by, target, wait=1)
        self.result['topics'] = len(elements)

    def _get_readme_name(self):
        conditions = EC.presence_of_element_located
        by = By.CSS_SELECTOR
        target = 'h2.Box-title.pr-3'
        element = self._get_elements(conditions, by, target, wait=1)

        if not element:
            self.result['readme'] = ''
            return
        return element.text   

    def _get_all_issue_pr(self):
        self._get_label_milestone()
        for type_ in ['issue', 'pr']:
            for recent in [False, True]:
                self._get_issue_pr(type_, recent)

    def _get_label_milestone(self):
        self._get_page_by_browser('/issues')
        soup = BeautifulSoup(self.browser.page_source, "html.parser")

        soup_list = self._get_element_from_page(soup, 'span', 'Counter d-none d-md-inline')

        self.result['labels'] = self._get_item(soup_list, 0)
        self.result['milestones'] = self._get_item(soup_list, 1)

    def _get_issue_pr(self, type_, recent=False):
        if type_ == 'issue':
            endpoint = '/issues?q=is%3Aissue+'
            key = 'issues'
        if type_ == 'pr':
            endpoint = '/issues?q=is%3Apr+'
            key = 'prs'
        if recent:
            endpoint += 'created%3A>%3D' + self.start_date + '+'
            key += '_recent'
        self._get_page_by_browser(endpoint)
        soup = BeautifulSoup(self.browser.page_source, "html.parser")

        if (self.browser.title.find('Pull') != -1 and type_ == 'issue') or (self.browser.title.find('Issue') != -1 and type_ == 'pr'):
            return
        soup_list = self._get_element_from_page(soup, 'a', 'btn-link')

        self.result['open_' + key] = self._get_item(soup_list, 0, 2)
        self.result['closed_' + key] = self._get_item(soup_list, 1, 2)

    def _get_insights(self):
        #self._get_recent_contributors()
        self._get_dependents()

    @staticmethod
    def age(first_date):
        days = (datetime.datetime.now() - parse(first_date)).days
        return days

    def _get_age_link(self):
        endpoint = ''
        conditions = EC.presence_of_element_located
        by = By.CSS_SELECTOR
        target = 'a.link-gray.text-mono'

        element = self._get_elements(conditions, by, target, wait=0)
        
        endpoint = '/commits/' + self.default_branch
        if self.result['commits'] >= 2:
            endpoint += '?after=' + element.get_attribute('href').split('/')[-1] + '+' + str(self.result['commits']-2)
        return endpoint

    def _get_age(self, endpoint):
        self._get_page_by_browser(endpoint)
        conditions = EC.presence_of_element_located
        by = By.CSS_SELECTOR
        target = 'h2.text-normal'

        element = self._get_elements(conditions, by, target)
        first_date = element.text[11:]
        self.result['age'] = self.age(first_date)
        if not self.result['age']:
            raise Exception('No age.')

    def _get_recent_contributors(self):
        from_ = self.start_date
        to_ = datetime.datetime.today().isoformat()[:10]
        endpoint = '/graphs/contributors?from=' + from_ + '&to=' + to_ + '&type=c'
        conditions = text_is_different
        by = By.TAG_NAME
        target = 'h2'
        custom = 'Loading contributions…'

        self._get_page_by_browser(endpoint)
        elements = self._get_elements(conditions, by, target, custom, wait=20)
        if not elements:
            #raise Exception("Failed to load contributors.")
            print('Failed to load contributors.')
            pass
        soup = BeautifulSoup(self.browser.page_source, 'html.parser')
        find_tag = soup.find_all('span', class_='cmeta')
        soup_list = list(find_tag)

        commits = []
        added = []
        deleted = []
        for i in range(len(soup_list)):
             num_commits = self._get_complex_item(soup_list, i, 0)
             num_added = self._get_complex_item(soup_list, i, 2)
             num_deleted = self._get_complex_item(soup_list, i, 4)
             if num_commits == 0:
                 break
             commits.append(num_commits)
             added.append(num_added)
             deleted.append(num_deleted)

        self.result['recent_contributors'] = len(commits)
        self.result['recent_commits'] = sum(commits)
        self.result['recent_added'] = sum(added)
        self.result['recent_deleted'] = sum(deleted)

    def _get_dependents(self):
        endpoint = '/network/dependents'
        conditions = text_has_numbers
        by = By.CSS_SELECTOR
        target = 'a.btn-link'
        custom = [0, 1]
        feature_names = ['dependent_repositories', 'dependent_packages']
        self._get_page_by_browser(endpoint)
        elements = self._get_elements(conditions, by, target, custom)
        self._update_result(elements, custom, feature_names)

    def _get_page_by_API(self, endpoint):
        url = self.BASE_API_URL + self.owner_repo + endpoint
        self.browser.get(url)
        soup = BeautifulSoup(self.browser.page_source, "html.parser")
        page = json.loads(soup.find("body").text)
        if 'message' in page:
            if 'API rate limit' in page['message']:
                raise Exception('Rate limit.')
            
        return page

    def _get_repo(self):
        endpoint = ''
        page = self._get_page_by_API(endpoint)
        if 'message' in page:
            self.result['info'] =  page['message']
            return

        if page['full_name'] != self.owner_repo:
            self.result['info'] = page['full_name']
            self.owner_repo = page['full_name']
        self.result['size'] = page['size']
        self.result['stars'] = page['stargazers_count']
        self.result['watches'] = page['subscribers_count']
        self.result['forks'] = page['forks']
        self.result['owner_type'] = page['owner']['type']
        self.result['if_fork'] = page['fork']
        self.result['has_issues'] = page['has_issues']
        self.result['description'] = page['description']
        self.result['homepage'] = page['homepage']
        self.result['license'] = page['license']
        self.result['language'] = page['language']
        self.result['mirror_url'] = page['mirror_url']
        self.result['archived'] = page['archived']
        self.result['disabled'] = page['disabled']

        self.default_branch = urllib.parse.quote(page['default_branch'])

    def _get_commits(self):
        endpoint = '/stats/commit_activity'
        page = self._get_page_by_API(endpoint)
        self.result['recent_commits'] = page

    def _get_files(self):
        endpoint = '/git/trees/' + self.default_branch + '?recursive=1'
        page = self._get_page_by_API(endpoint)
        if 'message' in page:
            self.result['info'] = 'Empty'
            return
        page = page['tree']
        
        if self.result['size'] == 0:
            size = 0
            for item in page:
                if item['type'] == 'tree':
                    continue
                size += item['size']

            self.result['size'] = size

        files = 0
        formats = {}
        i=-1
        for item in page:
            i+=1
            if item['type'] == 'tree':
                continue
            files += 1
            name = item['path'].split('.')
            #Do not include 'xx', '.xx', 'xx/.xx', 'xx.xx/xx'
            if len(name) == 1 or (len(name) == 2 and name[0] == '') or (name[-2] and name[-2][-1] == '/') or '/' in name[-1]:
                fmt = ''
            else:
                fmt = name[-1]
                fmt = fmt.lower()
            formats[fmt] = formats.get(fmt, 0) + 1

        self.result['formats'] = formats
        self.result['files'] = files

    def _get_readme(self):
        endpoint = '/readme'
        page = self._get_page_by_API(endpoint)
        if 'message' in page:
            return
        self.result['readme_name'] = page['name']
        self.result['readme_size'] = page['size']
        self._get_readme_file()

    def _get_readme_file(self):
        try:
            self.browser.get('https://raw.githubusercontent.com/' + self.owner_repo + '/' + self.default_branch + '/' + self.result['readme_name'])
        except:
            self.result['readme'] = ''
            return
        conditions = EC.presence_of_element_located
        by = By.CSS_SELECTOR
        target = 'pre'
        element = self._get_elements(conditions, by, target)
        if not element or element.text == '404: Not Found':
            self.result['readme'] = ''
        else:
            self.result['readme'] = element.text.replace('\n', '\xfe')

    def _get_community(self):
        endpoint = '/community/profile'
        page = self._get_page_by_API(endpoint)
        self.result['health_percentage'] = page['health_percentage']
       
    def _get_API(self):
        self._get_repo()
        if 'info' in self.result and self.result['info'] in ["Not Found", "Repository access blocked", "Empty"]:
            return
        self._get_commits()
        self._get_files()
        if 'info' in self.result and self.result['info'] in ["Not Found", "Repository access blocked", "Empty"]:
            return
        self._get_readme()
        self._get_community()

    def _get_owner(self):
        endpoint = '/..'
        conditions = text_has_numbers
        by = By.CSS_SELECTOR

        self._get_page_by_browser(endpoint)

        if self.result['owner_type'] == 'Organization':
            custom = [0]
            #target = 'span.js-profile-repository-count'
            #elements = self._get_elements(conditions, by, target, custom)
            #self._update_result(elements, custom, ['repositories'])


            target = 'a.UnderlineNav-item>span.js-profile-member-count'

            try:
                elements = WebDriverWait(self.browser, 1).until(
                             conditions((by, target)) if not custom else conditions((by, target), custom)
                             )
                self._update_result(elements, custom, ['people'])
            except:
                self.result['people'] = 0
        else:
            target = 'span.text-bold'
            custom = [0]
            feature_names = ['followers']
            elements = self._get_elements(conditions, by, target, custom)
            if not elements:
                self.result['followers'] = 0
            else:
                self._update_result(elements, custom, feature_names)


    def get_features(self):
        self._get_API()
        if 'info' in self.result and self.result['info'] in ["Not Found", "Repository access blocked", "Empty"]:
            return
        self._get_code()
        if 'info' in self.result and self.result['info'] in ["Not Found", "Repository access blocked", "Empty"]:
            return
        self._get_all_issue_pr()
        self._get_insights()
        self._get_owner()

