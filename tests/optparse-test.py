#!/usr/bin/python3
# -*- coding: utf-8 -*-

import sys
from optparse import OptionParser

if __name__ == '__main__':
    args = sys.argv[1:]
    # 读取除文件地址外得参数

    usage = "This is test!"  # 使用方法字符串
    optParser = OptionParser(usage)  # 创建一个对象 并把usage传进去

    # 添加规则
    optParser.add_option('-f', '--file', type="string", dest='filename', help="请输入文件路径")
    optParser.add_option("-u", "--url", dest="url", default='http://www.baidu.com', help="请输入目标网址")
    optParser.add_option("-e", "--exist", dest="exist", action="store_true", help="测试是否存在")
    optParser.add_option("-d", "--data", dest="data", help="数据")

    # 解析
    option, args = optParser.parse_args(args)
    print(option)
    print(args)