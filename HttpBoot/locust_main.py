#!/usr/bin/python3
# -*- coding: utf-8 -*-
import os
import sys
from pyutilb import log

def main():
    try:
        # 步骤yaml
        if len(sys.argv) > 1:
            yml_file = sys.argv[1]
        else:
            raise Exception("未指定步骤配置文件或目录")

        # locust_file
        #locust_file = os.path.abspath('locust_boot.py')
        locust_file = __file__.replace('locust_main.py', 'locust_boot.py')

        # 其他命令选项
        options = ''
        if len(sys.argv) > 2:
            options = ' '.join(sys.argv[2:])

        # 执行locust命令
        cmd = f'locust -f {locust_file} -b {yml_file} {options}'
        log.debug(cmd)
        os.system(cmd)
    except Exception as ex:
        log.error(f"异常环境:当前步骤文件为 {yml_file}", exc_info = ex)
        raise ex

if __name__ == '__main__':
    main()