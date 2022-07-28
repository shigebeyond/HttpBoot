#!/usr/bin/python3
# -*- coding: utf-8 -*-

import json
import requests
import re

class Login():
    def __init__(self):
        self.session = requests.session()
        self.host = 'http://admin.jym0.com/'

    # 获取验证码
    def getcode(self):
        # 刷新验证码（要先刷新，不然会报验证码不正确）
        verify_images = self.host + '/login/verify_image'
        res = self.session.get(verify_images)
        # 获取验证码
        url = self.host + 'login/verify_code'
        res = self.session.get(url).text  # 拿到的是json
        jsonEx = json.loads(res)  # 将json转化为字典
        perentCode = jsonEx['data']['code']
        return perentCode

    # 登录
    def login(self, account='18877310999', passwd='e10adc3949ba59abbe56e057f20f883e', verify_text=''):
        url = self.host + '/login/check'
        verify_text = self.getcode() # 获得验证码
        data = {'account': account, 'passwd': passwd, 'verify_text': verify_text}
        res = self.session.post(url, data=data)
        print(res.json())  # 这里一定要记得return，不然结果值传递不下去

    # 首页
    def home(self):
        url = self.host + '/home/'
        res = self.session.post(url)
        text = res.text
        # print(text)
        m = re.search(r'<div class="last-login-time">上次登录时间：([^>]+)</div>', text, re.M | re.I)
        dtime = m.group(1)
        print('爬到登录时间为：' + dtime)

# 调试
if __name__ == '__main__':
    lg = Login()
    lg.login()
    lg.home()
