#!/usr/bin/python3
# -*- coding: utf-8 -*-

import os
import sys
import fnmatch
import requests
from pyutilb.util import *
from HttpBoot.validator import Validator
from HttpBoot.extractor import Extractor
from requests.sessions import Session
import curlify
import threading
from pyutilb import log, YamlBoot, ocr_youdao
if hasattr(os, 'posix_spawnp'):
    import gevent
    from locust.clients import HttpSession

# 改造 requests.Session.request() -- 支持打印curl + fix get请求不能传递data + fix不能传递cookie
if Session.request.__name__ != 'request2': # fix bug: 两次执行此处, 从而导致 Session.request 被改写两次, 从而导致打了2次log
    request1 = Session.request
    def request2(self, method, url, name=None, **kwargs):
        # fix bug： get请求不能传递data
        if method.upper() == 'GET' and 'data' in kwargs and kwargs['data']:
            data = kwargs['data']
            # 将data转为query string
            if '?' in url:
                query_string = '&'
            else:
                query_string = '?'
            for k, v in data.items():
                query_string += f"{k}={v}&"
            url += query_string
            kwargs['data'] = None

        # fix bug: 不能传递cookie
        if 'headers' in kwargs and kwargs['headers'] != None and 'cookie' in kwargs['headers']:
            cookie = kwargs['headers']['cookie']
            kwargs['cookies'] = dict([l.split("=", 1) for l in cookie.split("; ")])  # cookie字符串转化为字典

        # 请求
        res = request1(self, method, url, name, **kwargs)

        # 打印curl
        cmd = curlify.to_curl(res.request)
        log.debug('send request: ' + cmd)
        return res
    Session.request = request2

# 跳出循环的异常
class BreakException(Exception):
    def __init__(self, condition):
        self.condition = condition # 跳转条件

# http接口基于yaml的启动器
class HttpBoot(YamlBoot):

    def __init__(self):
        super().__init__()
        # 动作映射函数
        actions = {
            'base_url': self.base_url,
            'common_data': self.common_data,
            'common_headers': self.common_headers,
            'get': self.get,
            'post': self.post,
            'upload': self.upload,
            'download': self.download,
            'recognize_captcha': self.recognize_captcha,
            'concurrent': self.concurrent,
        }
        self.add_actions(actions)

        # 已下载过的url对应的文件，key是url，value是文件
        self.downloaded_files = {}
        # 基础url
        self._base_url = None
        # 公共请求参数
        self._common_data = None
        # 公共请求头
        self._common_headers = None
        # 当前url
        self.curr_url = None
        # 当前session
        self.session = requests.Session()
        # 记录响应时间
        self.res_times = []
        # 错误次数
        self.err_num = 0

    # --------- 动作处理的函数 --------
    # 并发测试
    # :param steps 每个迭代中要执行的步骤
    # :param args 其他参数，包含2个数: 1 concurrency 并发数 2 req_num 每个线程的请求数
    def concurrent(self, steps, args):
        if args == None or len(args) < 2:
            raise Exception(f'Miss concurrency and req_num parameter')

        concurrency = int(args[0]) # 并发数
        req_num = int(args[1]) # 每个线程的请求数
        log.debug(f"-- Concurrent({concurrency},{req_num}) start --")
        # 清空响应时间+错误次数
        self.res_times.clear()
        self.err_num = 0

        # 每个线程的处理
        def run_thread():
            for i in range(0, req_num):
                t1 = time.time()
                try:
                    self.run_steps(steps)
                except Exception as e:
                    log.error('并发单个请求异常', exc_info = e)
                    self.err_num += 1
                finally:
                    t2 = time.time()
                    # 记录响应时间
                    self.res_times.append(t2 - t1)

        # 创建并发的线程
        t1 = time.time()
        threads = []
        for i in range(concurrency):
            # 新启线程执行： self.run_steps(steps)
            # t = threading.Thread(target=self.run_steps, args=(steps), name="Test" + str(i))
            t = threading.Thread(target=run_thread, name="Test" + str(i))
            threads.append(t)
        for t in range(concurrency):
            threads[t].start()
        for j in range(concurrency):
            threads[j].join()
        t2 = time.time()
        n = len(self.res_times)
        cost_time = t2 - t1
        log.debug(f"-- Concurrent({concurrency},{req_num}) finish --")
        log.debug("total costtime(s): %s", cost_time)
        log.debug('response num: %s', n)
        log.debug('success num: %s', n - self.err_num)
        log.debug('fail num: %s', self.err_num)
        log.debug('max costtime(s): %s', max(self.res_times))
        log.debug('min costtime(s): %s', min(self.res_times))
        log.debug('avg costtime(s): %s', sum(self.res_times) / n)
        log.debug('throughput: %s', n / cost_time) # 吞吐量

    # 解析响应
    def _analyze_response(self, res, config):
        # 添加固定变量:响应
        set_var('response', res)
        # 校验器
        v = Validator(res)
        v.run(config)
        # 提取器
        e = Extractor(res)
        e.run(config)

    # 设置基础url
    def base_url(self, url):
        self._base_url = url

    # 拼接url
    def _get_url(self, config):
        url = config['url']
        url = replace_var(url)  # 替换变量
        # 添加基url
        if (self._base_url is not None) and ("http" not in url):
            url = self._base_url + url
        self.curr_url = url
        return url

    # 设置公共请求参数
    # :param data
    def common_data(self, data):
        # self.session.params = replace_var(data, False) # 只挂在url的query参数中
        self._common_data = replace_var(data, False) # 如果是get请求, 则挂在query参数, 否则挂在post参数中

    # 构建参数
    def _get_data(self, config):
        if 'data' not in config:
            return self._common_data

        # 当前参数
        curr_data = replace_var(config['data'], False)
        # 合并公共参数
        if isinstance(self._common_data, dict):
            r = {}
            r.update(self._common_data)
            r.update(curr_data) # 公共参数会被当前参数覆盖
            return r

        return curr_data

    # 设置公共请求头
    # :param headers
    def common_headers(self, headers):
        # 经测试:两种实现是一样效果的
        # self.session.headers = replace_var(headers, False)
        self._common_headers = replace_var(headers, False)

    # 构建参数
    def _get_headers(self, config):
        if 'headers' not in config:
            return self._common_headers

        # 当前参数
        curr_headers = replace_var(config['headers'], False)
        # 合并公共参数
        if isinstance(self._common_headers, dict):
            r = {}
            r.update(self._common_headers)
            r.update(curr_headers)  # 公共参数会被当前参数覆盖
            return r

        return curr_headers

    # 构建requests方法的其他参数
    # 如 verify: false 控制不检查https证书
    # 如 allow_redirects: false 不允许重定向
    def _get_options(self, config):
        opt = None
        if 'options' in config:
            opt = config['options']
        if opt == None:
            opt = {}
        return opt

    # get请求
    # :param config {url, headers, data, validate_by_jsonpath, validate_by_css, validate_by_xpath, extract_by_jsonpath, extract_by_css, extract_by_xpath, extract_by_eval}
    def get(self, config = {}):
        url = self._get_url(config)
        data = self._get_data(config)
        headers = self._get_headers(config)
        opt = self._get_options(config)
        res = self.session.get(url, headers=headers, data=data, **opt)
        # log.debug(res.text)
        # 解析响应
        self._analyze_response(res, config)

    # post请求
    # :param config {url, headers, data, validate_by_jsonpath, validate_by_css, validate_by_xpath, extract_by_jsonpath, extract_by_css, extract_by_xpath, extract_by_eval}
    def post(self, config = {}):
        url = self._get_url(config)
        data = self._get_data(config)
        headers = self._get_headers(config)
        opt = self._get_options(config)
        res = self.session.post(url, headers=headers, data=data, **opt)
        # 解析响应
        self._analyze_response(res, config)

    # 上传文件
    # :param config {url, headers, files, validate_by_jsonpath, validate_by_css, validate_by_xpath, extract_by_jsonpath, extract_by_css, extract_by_xpath, extract_by_eval}
    def upload(self, config = {}):
        url = self._get_url(config)
        headers = self._get_headers(config)
        # 文件
        files = {}
        for name, path in config['files'].items():
            path = replace_var(path)
            files[name] = open(path, 'rb')
        # 发请求
        opt = self._get_options(config)
        res = self.session.post(url, headers=headers, files=files, **opt)
        # 解析响应
        self._analyze_response(res, config)

    # 下载文件
    # :param config {url, save_dir, save_file}
    def download(self, config={}):
        url = self._get_url(config)
        data = self._get_data(config)
        headers = self._get_headers(config)

        # 文件名
        save_file = self._prepare_save_file(config, url)
        # 真正的下载
        if url in self.downloaded_files:
            return self.downloaded_files[url]

        # 发请求
        opt = self._get_options(config)
        res = self.session.get(url, headers=headers, data=data, **opt)

        # 保存响应的文件
        write_byte_file(save_file, res.content)
        # 设置变量
        set_var('download_file', save_file)
        self.downloaded_files[url] = save_file
        log.debug(f"Dowload file: url is {url}, save path is{save_file}")
        return save_file

    # 获得文件名
    # config['save_dir'] + config['save_file'] 或 url中的默认文件名
    def _prepare_save_file(self, config, url):
        # 获得保存的目录
        if 'save_dir' in config:
            save_dir = config['save_dir']
        else:
            save_dir = 'downloads'
        # 获得保存的文件名
        if 'save_file' in config:
            save_file = config['save_file']
        else:
            save_file = os.path.basename(url)
        save_file = os.path.abspath(save_dir + os.sep + save_file)  # 转绝对路径
        # 准备目录
        dir, name = os.path.split(save_file)
        if not os.path.exists(dir):
            os.makedirs(dir)
        # 检查重复
        if os.path.exists(save_file):
            for i in range(100000000000000):
                if '.' in save_file:
                    path, ext = save_file.rsplit(".", 1) # 从后面分割，分割为路径+扩展名
                    newname = f"{path}-{i}.{ext}"
                else:
                    newname = f"{save_file}-{i}"
                if not os.path.exists(newname):
                    return newname
            raise Exception('Too many file in save_dir, please change other directory.')

        return save_file

    # 识别url中的验证码
    def recognize_captcha(self, config={}):
        # 下载图片
        file = self.download(config)
        # 识别验证码
        self._do_recognize_captcha(file)

    # 真正的识别验证码
    def _do_recognize_captcha(self, file_path):
        # 1 使用 pytesseract 识别图片 -- wrong: 默认没训练过的识别不了
        # img = Image.open(file_path)
        # captcha = pytesseract.image_to_string(img)
        # 2 使用有道ocr
        captcha = ocr_youdao.recognize_text(file_path)
        # 设置变量
        set_var('captcha', captcha)
        log.debug(f"Recognize captcha: image file is {file_path}, captcha is {captcha}")
        # 删除文件
        #os.remove(file)

# cli入口
def main():
    # 基于yaml的执行器
    boot = HttpBoot()
    # 读元数据：author/version/description
    dir = os.path.dirname(__file__)
    meta = read_init_file_meta(dir + os.sep + '__init__.py')
    # 步骤配置的yaml
    step_files = parse_cmd('HttpBoot', meta['version'])
    if len(step_files) == 0:
        raise Exception("Miss step config file or directory")
    try:
        # 执行yaml配置的步骤
        boot.run(step_files)
    except Exception as ex:
        log.error(f"Exception occurs: current step file is {boot.step_file}, current url is {boot.curr_url}", exc_info = ex)
        raise ex

if __name__ == '__main__':
    main()