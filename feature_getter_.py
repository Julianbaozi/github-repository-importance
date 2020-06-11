import time

import requests
from bs4 import BeautifulSoup
import re

import datetime
from dateutil.parser import parse

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
            with open('log.txt', 'a') as f:
                f.write(driver.page_source)
            return False

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
            with open('log.txt', 'a') as f:
                f.write(driver.page_source)
            return False
        actual_text = elements[0].text
        return elements if actual_text != self.text else False


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
        self.result = {'name': owner_repo}

    def __call__(self):
        self.get_features()

    @staticmethod
    def _get_item(soup_list, index, content_index=0):
        return int(re.findall('[0-9,]+', soup_list[index].contents[content_index])[0].replace(',', ''))

    @staticmethod
    def _get_complex_item(soup_list, index, content_index=0):
        return int(re.findall('[0-9,]+', soup_list[index].contents[content_index].contents[0])[0].replace(',', ''))

    def _get_elements(self, conditions, by, target, custom=None):
        elements = None
        for i in range(2):
                try:
                        elements = WebDriverWait(self.browser, 10).until(
                                conditions((by, target)) if not custom else conditions((by, target), custom)
                            )
                        break
                except:
                    print('Loading timeout. URL: ' + self.browser.current_url, '. Tried ' + str(i + 1) + ' times.')

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
        conditions = text_has_numbers
        by = By.CSS_SELECTOR
        target = 'span.num.text-emphasized'
        custom = [0, 1, 3, 4]
        feature_names = ['commits', 'branches', 'releases', 'contributors']

        self._get_page_by_browser(endpoint)
        elements = self._get_elements(conditions, by, target, custom)
        self._update_result(elements, custom, feature_names)

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
        if self._get_age():
            self._get_recent_contributors()
        self._get_dependents()

    @staticmethod
    def age(first_date):
        days = (datetime.datetime.now() - parse(first_date)).days
        return days

    def _get_age(self):
        endpoint = '/graphs/contributors'
        conditions = text_is_different
        by = By.TAG_NAME
        target = 'h2'
        custom = 'Loading contributions…'

        self._get_page_by_browser(endpoint)

        elements = self._get_elements(conditions, by, target, custom)
        if not elements:
            conditions = EC.presence_of_element_located
            by = By.CSS_SELECTOR
            target = 'div.graph-empty msg mt-6'
            try:
                _ = WebDriverWait(self.browser, 1).until(conditions((by, target)))        
                return False
            except:
                pass
        
        else:
            first_date = elements[0].text.split('–')[0]
            self.result['age'] = self.age(first_date)
            return True

    def _get_recent_contributors(self):
        from_ = self.start_date
        to_ = datetime.datetime.today().isoformat()[:10]
        endpoint = '/graphs/contributors?from=' + from_ + '&to=' + to_ + '&type=c'
        conditions = text_is_different
        by = By.TAG_NAME
        target = 'h2'
        custom = 'Loading contributions…'

        self._get_page_by_browser(endpoint)
        self._get_elements(conditions, by, target, custom)
        
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

    def _get_repo(self):
        url = self.BASE_API_URL + self.owner_repo
        self.browser.get(url)
        soup = BeautifulSoup(self.browser.page_source, "html.parser")
        page = json.loads(soup.find("body").text)
        if 'message' in page and page['message'] == "Not Found":
            self.result['info'] = "Not Found"
            return
        if page['full_name'] != self.owner_repo:
            self.result['info'] = self.owner_repo
            self.owner_repo = page['full_name']
        self.result['size'] = page['size']
        self.result['stars'] = page['stargazers_count']
        self.result['watches'] = page['subscribers_count']
        self.result['forks'] = page['forks']
        self.result['owner_type'] = page['owner']['type']
        self.result['if_fork'] = page['fork']

    def _get_owner(self):
        endpoint = '/..'
        conditions = text_has_numbers
        by = By.CSS_SELECTOR

        self._get_page_by_browser(endpoint)

        if self.result['owner_type'] == 'Organization':
            custom = [0]
            target = 'a.pagehead-tabs-item>span.js-profile-repository-count'
            elements = self._get_elements(conditions, by, target, custom)
            self._update_result(elements, custom, ['repositories'])


            target = 'a.pagehead-tabs-item>span.js-profile-member-count'
        
            try:
                elements = WebDriverWait(self.browser, 1).until(
                             conditions((by, target)) if not custom else conditions((by, target), custom)
                             )
                self._update_result(elements, custom, ['people'])
            except:
                pass
        else:
            target = 'span.Counter'
            custom = [0, 3]
            feature_names = ['repositories', 'followers']
            elements = self._get_elements(conditions, by, target, custom)
            self._update_result(elements, custom, feature_names)

    def get_features(self):
        self._get_repo()
        if 'info' in self.result and self.result['info'] == "Not Found":
            return
        self._get_code()
        self._get_all_issue_pr()
        self._get_insights()
        self._get_owner()

