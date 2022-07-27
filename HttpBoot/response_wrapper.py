#!/usr/bin/python
# -*- coding: utf-8 -*-

import re
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
            # html = etree.parse(self.res.text, etree.HTMLParser()) # parse的是html文件
            html = etree.fromstring(self.res.text, etree.HTMLParser()) # fromstring的是html文本
            return html.cssselect(path)[0].text

        if type == 'xpath':
            # 检查xpath是否最后有属性
            mat = re.search('/@[\w\d_]+$', path)
            prop = ''
            if (mat != None):  # 有属性
                # 分离元素path+属性
                prop = mat.group()
                path = path.replace(prop, '')
                prop = prop.replace('/@', '')

            html = etree.fromstring(self.res.text, etree.HTMLParser())
            ele = html.xpath(path)[0]
            if prop != '': # 获得属性
                return ele.get(prop)
            return ele.text

        if type == 'jsonpath':
            data = self.res.json()
            return jsonpath(data, path)[0]

        if type == 'id':
            html = etree.parse(self.res.text, etree.HTMLParser())
            return html.get_element_by_id(path).text

        raise Exception(f"不支持查找类型: {type}")