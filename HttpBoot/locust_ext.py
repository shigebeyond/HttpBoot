#!/usr/bin/python3
# -*- coding: utf-8 -*-

import os
from locust import HttpUser, TaskSet, task
from util import *
from boot import Boot

# 切换当前目录
dir = os.path.dirname(__file__)
os.chdir(dir)

# 读取配置文件
config_file = os.path.abspath('locust.yml')
config = read_yaml(config_file)

# 根据步骤生成locust任务函数
def build_task(steps):
    def run_task(self):
        self.boot.run_steps(steps)
    return run_task

class BootUser(HttpUser):
    tasks = [build_task(config['task'])] # task下的多个步骤只当做一个任务，反正locust监控的是请求级，而不是任务级
    host = config['base_url']
    min_wait = 1000
    max_wait = 5000

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 引用boot
        self.boot = Boot()
        # 改写session
        self.boot.session = self.client

    def on_start(self):
        if 'on_start' in config:
            self.boot.run_steps(config['on_start'])

    def on_stop(self):
        if 'on_stop' in config:
            self.boot.run_steps(config['on_stop'])

if __name__ == '__main__':
    os.system(r'locust -f ' + __file__)