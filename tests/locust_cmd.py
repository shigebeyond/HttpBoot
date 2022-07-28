#!/usr/bin/python3
# -*- coding: utf-8 -*-

import os
from locust import HttpUser, TaskSet, task
from locust.main import main

class WebsiteTasks(TaskSet):
    def on_start(self):
        print('start')

    @task(2)
    def bank(self):
        self.client.get("/home/get_bank_list")

    @task(1)
    def home(self):
        self.client.get("/home/")

class WebsiteUser(HttpUser):
    # task_set = WebsiteTasks
    tasks = [WebsiteTasks]
    host = "http://api.jym0.com/"
    min_wait = 1000
    max_wait = 5000

if __name__ == '__main__':
    os.system(r'locust -f ' + __file__)