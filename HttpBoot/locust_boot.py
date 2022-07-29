#!/usr/bin/python3
# -*- coding: utf-8 -*-

import os
import sys
from locust import HttpUser, TaskSet, task, argument_parser,events
from HttpBoot.util import *
from HttpBoot.http_boot import HttpBoot

# 1 如果是启动类+非locust命令, 则启动locust命令, 但忽略后续locust业务处理代码(如user类)
# fix bug: locust_boot.main()与http_boot.main()重名会覆盖, 因此调整命名
def lmain():
    # 步骤yaml
    if len(sys.argv) > 1:
        yml_file = sys.argv[1]
    else:
        raise Exception("未指定步骤配置文件或目录")
    # 执行locust命令
    cmd = f'locust -f {__file__} -b {yml_file}'
    print(cmd)
    os.system(cmd)
    exit()
if __name__ == '__main__' and sys.argv[0] != 'locust':
    lmain()

# 2 如果是非启动类+locust命令, 则调用locust业务处理代码(如user类)
# 将步骤yml添加为locust参数, 这样locust命令才不会校验报错
@events.init_command_line_parser.add_listener
def _(parser):
    parser.add_argument(
        "-b",
        "--bootyml",
        default="locust.yml",
        help="Boot steps yaml file. Defaults to 'locust.yml'",
        env_var="LOCUST_BOOT_YML",
    )
# 解析locust参数, 获得步骤yml
options = argument_parser.parse_options(sys.argv)
# print(options.bootyml)

# 读取步骤yml
config_file = os.path.abspath(options.bootyml)
config = read_yaml(config_file)

# 根据步骤生成locust任务函数
def build_task(steps):
    def run_task(self):
        self.boot.run_steps(steps)
    return run_task

# user类
class BootUser(HttpUser):
    tasks = [build_task(config['task'])] # task下的多个步骤只当做一个任务，反正locust监控的是请求级，而不是任务级
    host = config['base_url']
    min_wait = 1000
    max_wait = 5000

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 引用boot
        self.boot = HttpBoot()
        # 改写session
        self.boot.session = self.client

    def on_start(self):
        if 'on_start' in config:
            self.boot.run_steps(config['on_start'])

    def on_stop(self):
        if 'on_stop' in config:
            self.boot.run_steps(config['on_stop'])
