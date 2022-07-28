#!/usr/bin/python3
# -*- coding: utf-8 -*-

import os
from locust import HttpUser, TaskSet, task
from locust.main import main

def bank(self):
    self.client.get("/home/get_bank_list")

def home(self):
    self.client.get("/home/")

class WebsiteUser(HttpUser):
    tasks = [bank, home]
    host = "http://api.jym0.com/"
    min_wait = 1000
    max_wait = 5000

    def on_start(self):
        print('start')

if __name__ == '__main__':
    os.system(f'locust -f {__file__}')