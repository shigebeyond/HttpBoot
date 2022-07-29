#!/usr/bin/python3
# -*- coding: utf-8 -*-
import os
import sys
from pyutilb import log

def main():
    # 步骤yaml
    if len(sys.argv) > 1:
        yml_file = sys.argv[1]
    else:
        raise Exception("未指定步骤配置文件或目录")

    # locust_file
    #locust_file = os.path.abspath('locust_boot.py')
    locust_file = __file__.replace('locust_main.py', 'locust_boot.py')

    # 执行locust命令
    cmd = f'locust -f {locust_file} -b {yml_file}'
    log.debug(cmd)
    os.system(cmd)

if __name__ == '__main__':
    main()