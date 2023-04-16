#!/usr/bin/python3
# -*- coding: utf-8 -*-
import os
import sys
from pyutilb.log import log
from pyutilb.util import *
from pyutilb.file import *
from pyutilb.cmd import *

def main():
    try:
        # 读元数据：author/version/description
        dir = os.path.dirname(__file__)
        meta = read_init_file_meta(dir + os.sep + '__init__.py')

        # 步骤配置的yaml
        step_files, option = parse_cmd('LocustBoot', meta['version'])
        if len(step_files) == 0:
            raise Exception("Miss step config file")
        step_file = step_files[0]

        # 运行locust命令
        run_locust_boot(step_file, option.locustopt)
    except Exception as ex:
        log.error(f"Exception occurs: current step file is {step_file}", exc_info = ex)
        raise ex

# 运行locust命令
def run_locust_boot(step_file, options):
    # locust_file
    # locust_file = os.path.abspath('locust_boot.py')
    locust_file = __file__.replace('locust_main.py', 'locust_boot.py')
    # 执行locust命令
    cmd = f'locust -f {locust_file} -b {step_file} {options}'
    log.debug(cmd)
    os.system(cmd)


if __name__ == '__main__':
    main()