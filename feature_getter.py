import time

import requests
from bs4 import BeautifulSoup
import re

import datetime
from dateutil.parser import parse

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from conf import TIME_DELTA


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

    @staticmethod
    def _get_item(soup_list, index, content_index=0):
        return int(re.findall('[0-9,]+', soup_list[index].contents[content_index])[0].replace(',', ''))

    @staticmethod
    def _get_complex_item(soup_list, index, content_index=0):
        return int(re.findall('[0-9,]+', soup_list[index].contents[content_index].contents[0])[0].replace(',', ''))

    def _get_page(self, endpoint):
        url = self.BASE_URL + self.owner_repo + endpoint

        page = requests.get(url, proxies=self.proxies)
        soup = BeautifulSoup(page.content, 'html.parser')
        return soup

    def _get_page_by_browser(self, endpoint, conditions, locator, wait_for):
        url = self.BASE_URL + self.owner_repo + endpoint
        self.browser.get(url)
        try:
            WebDriverWait(self.browser, 20).until(
                conditions((locator, wait_for))
            )
        except:
            print('Loading timeout. URL: ' + url)
        soup = BeautifulSoup(self.browser.page_source, 'html.parser')
        return soup

    @staticmethod
    def _get_element_from_page(soup, tag, class_name):
        find_tag = soup.find_all(tag, class_=class_name)
        soup_list = list(find_tag)
        return soup_list

    def _get_code(self):
        soup = self._get_page_by_browser('', conditions=EC.presence_of_element_located,
                                         locator=By.CSS_SELECTOR,
                                         wait_for='a[href="/' + self.owner_repo + '/graphs/contributors"]>span')
        soup_list = self._get_element_from_page(soup, 'span', 'num text-emphasized')

        self.result['commits'] = self._get_item(soup_list, 0)
        self.result['branches'] = self._get_item(soup_list, 1)
        self.result['releases'] = self._get_item(soup_list, 3)
        self.result['contributors'] = self._get_item(soup_list, 4)

        soup_list = self._get_element_from_page(soup, 'span', 'Counter')
        try:
            self.result['projects'] = self._get_item(soup_list, 2)
        except:
            self.result['projects'] = 0

    def _get_all_issue_pr(self):
        self._get_label_milestone()
        for type_ in ['issue', 'pr']:
            for recent in [False, True]:
                self._get_issue_pr(type_, recent)

    def _get_label_milestone(self):
        soup = self._get_page('/issues')
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
        soup = self._get_page(endpoint)
        soup_list = self._get_element_from_page(soup, 'a', 'btn-link')

        self.result['open_' + key] = self._get_item(soup_list, 0, 2)
        self.result['closed_' + key] = self._get_item(soup_list, 1, 2)

    def _get_insights(self):
        self._get_age()
        self._get_recent_contributors()
        self._get_dependents()

    @staticmethod
    def age(first_date):
        days = (datetime.datetime.now() - parse(first_date)).days
        return days

    def _get_age(self):
        soup = self._get_page_by_browser('/graphs/contributors', conditions=EC.presence_of_element_located,
                                         locator=By.CSS_SELECTOR, wait_for="rect.overlay")
        soup_list = self._get_element_from_page(soup, 'h2', 'Subhead-heading js-date-range')
        first_date = soup_list[0].contents[0].split('–')[0]

        self.result['age'] = self.age(first_date)

    def _get_recent_contributors(self):
        from_ = self.start_date
        to_ = datetime.datetime.today().isoformat()[:10]
        endpoint = '/graphs/contributors?from=' + from_ + '&to=' + to_ + '&type=c'
        soup = self._get_page_by_browser(endpoint, conditions=EC.presence_of_element_located,
                                         locator=By.CSS_SELECTOR, wait_for="rect.overlay")
        soup_list = self._get_element_from_page(soup, 'span', 'cmeta')

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
        soup = self._get_page('/network/dependents')
        soup_list = self._get_element_from_page(soup, 'a', 'btn-link')

        self.result['dependent_repositories'] = self._get_item(soup_list, 0, 2)
        self.result['dependent_packages'] = self._get_item(soup_list, 1, 2)

    def _get_repo(self):
        url = self.BASE_API_URL + self.owner_repo
        page = requests.get(url, proxies=self.proxies)
        page = page.json()
        self.result['size'] = page['size']
        self.result['stars'] = page['stargazers_count']
        self.result['watches'] = page['subscribers_count']
        self.result['forks'] = page['forks']
        self.result['owner_type'] = page['owner']['type']
        self.result['if_fork'] = page['fork']

    def _get_owner(self):
        owner = self.owner_repo.split('/')[0]
        url = self.BASE_URL + owner

        self.browser.get(url)
        time.sleep(1)
        soup = BeautifulSoup(self.browser.page_source, 'html.parser')
        if self.result['owner_type'] == 'Organization':
            find_tag = soup.find_all('a', class_='pagehead-tabs-item')
            soup_list = list(find_tag)

            self.result['repositories'] = self._get_complex_item(soup_list, 0, 3)
            self.result['people'] = self._get_complex_item(soup_list, 2, 3)
        else:
            find_tag = soup.find_all('span', class_='Counter hide-lg hide-md hide-sm')
            soup_list = list(find_tag)

            self.result['repositories'] = self._get_item(soup_list, 0)
            self.result['followers'] = self._get_item(soup_list, 3)

    def get_features(self):
        self._get_repo()

        self._get_code()
        self._get_all_issue_pr()
        self._get_insights()
        self._get_owner()

