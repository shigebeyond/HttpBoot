#!/usr/bin/python3
# -*- coding: utf-8 -*-
import os
import sys
from pyutilb import log
from pyutilb.util import *

def main():
    try:
        # 读元数据：author/version/description
        dir = os.path.dirname(__file__)
        meta = read_init_file_meta(dir + os.sep + '__init__.py')
        # 步骤配置的yaml
        step_files = parse_cmd('LocustBoot', meta['version'])
        if len(step_files) == 0:
            raise Exception("未指定步骤配置文件")
        step_file = step_files[0]

        # locust_file
        #locust_file = os.path.abspath('locust_boot.py')
        locust_file = __file__.replace('locust_main.py', 'locust_boot.py')

        # 其他命令选项
        options = ''
        if len(sys.argv) > 2:
            options = ' '.join(sys.argv[2:])

        # 执行locust命令
        cmd = f'locust -f {locust_file} -b {step_file} {options}'
        log.debug(cmd)
        os.system(cmd)
    except Exception as ex:
        log.error(f"异常环境:当前步骤文件为 {step_file}", exc_info = ex)
        raise ex

if __name__ == '__main__':
    main()