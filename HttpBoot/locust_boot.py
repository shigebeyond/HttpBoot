#!/usr/bin/python3
# -*- coding: utf-8 -*-

import sys
from locust import HttpUser, FastHttpUser, argument_parser, events
from pyutilb.util import *
from pyutilb.file import *
from pyutilb.log import log
from HttpBoot.http_boot import HttpBoot

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
# log.debug(options.bootyml)

# 读取步骤yml
config_file = options.bootyml
config = read_yaml(config_file)

# 根据步骤生成locust任务函数
def build_task(steps):
    def run_task(self):
        self.boot.run_steps(steps)
    return run_task

# user类
# FastHttpUser 相对于 HttpUser 能提升5-6倍的并发量; 单个locust进程(1核cpu)下，FastHttpUser 可以做到16000 qps，HttpUser 做到 4000 qps
if hasattr(os, 'posix_spawnp'):
    log.info('使用协程压测')
    UserClass = FastHttpUser
else:
    log.info('使用线程压测')
    UserClass = HttpUser
class BootUser(UserClass):
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
        # 步骤文件目录: 如果不设置，则无法执行include动作
        if is_http_file(config_file):
            i = config_file.rindex('/')
            self.boot.step_dir = config_file[:i]
        else:
            self.boot.step_dir = os.path.dirname(os.path.abspath(config_file))
        # 使用文件缓存
        self.boot.use_file_cache(True)

    def on_start(self):
        if 'on_start' in config:
            self.boot.run_steps(config['on_start'])

    def on_stop(self):
        if 'on_stop' in config:
            self.boot.run_steps(config['on_stop'])
