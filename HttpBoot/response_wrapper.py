#!/usr/bin/python
# -*- coding: utf-8 -*-

import re
from pyutilb.util import *
from lxml import etree
from requests import Response
from jsonpath import jsonpath

# 响应包装器
class ResponseWrap(object):

    def __init__(self, res: Response = None):
        # 响应
        self.res = res

    # 获得元素值
    def _get_val_by(self, type, path):
        if type == 'css':
            path, prop = split_xpath_and_prop(path)
            # html = etree.parse(self.res.text, etree.HTMLParser()) # parse的是html文件
            html = etree.fromstring(self.res.text, etree.HTMLParser()) # fromstring的是html文本
            ele = html.cssselect(path)[0]
            return self.get_prop_or_text(ele, prop)

        if type == 'xpath':
            path, prop = split_xpath_and_prop(path)
            html = etree.fromstring(self.res.text, etree.HTMLParser())
            ele = html.xpath(path)[0]
            return self.get_prop_or_text(ele, prop)

        if type == 'jsonpath':
            data = self.res.json()
            return jsonpath(data, path)[0]

        if type == 'id':
            html = etree.parse(self.res.text, etree.HTMLParser())
            return html.get_element_by_id(path).text

        if type == 'eval':
            return eval(path, globals(), get_vars()) # 丢失本地与全局变量, 如引用不了json模块

        raise Exception(f"Invalid find type: {type}")


    # 获得元素的属性值或文本
    def get_prop_or_text(self, ele, prop):
        # 响应元素
        if isinstance(ele, etree._Element):
            if prop != '':  # 获得属性
                return ele.get(prop)
            return ele.text

        raise Exception('Invalid element')
