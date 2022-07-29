#!/usr/bin/python3
# -*- coding: utf-8 -*-

import gevent
import sys
import fnmatch
import requests
from pyutilb.util import *
from HttpBoot.validator import Validator
from HttpBoot.extractor import Extractor
from locust.clients import HttpSession
from requests.sessions import Session
import curlify
import threading
from pyutilb import log, ocr_youdao

# 改造 requests.Session.request() -- 支持打印curl + fix get请求不能传递data + fix不能传递cookie
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
    log.debug('发送请求：' + cmd)
    return res
Session.request = request2

# 跳出循环的异常
class BreakException(Exception):
    def __init__(self, condition):
        self.condition = condition # 跳转条件

# http接口基于yaml的启动器
class HttpBoot(object):

    def __init__(self):
        # 步骤文件所在的目录
        self.step_dir = None
        # 已下载过的url对应的文件，key是url，value是文件
        self.downloaded_files = {}
        # 基础url
        self._base_url = None
        # 公共请求参数
        self._common_data = None
        # 公共请求头
        self._common_headers = None
        # 动作映射函数
        self.actions = {
            'sleep': self.sleep,
            'print': self.print,
            'base_url': self.base_url,
            'common_data': self.common_data,
            'common_headers': self.common_headers,
            'get': self.get,
            'post': self.post,
            'upload': self.upload,
            'download': self.download,
            'recognize_captcha': self.recognize_captcha,
            'for': self.do_for,
            'once': self.once,
            'break_if': self.break_if,
            'moveon_if': self.moveon_if,
            'include': self.include,
            'set_vars': self.set_vars,
            'print_vars': self.print_vars,
            'concurrent': self.concurrent,
        }
        set_var('boot', self)
        # 当前url
        self.curr_url = None
        # 当前session
        self.session = requests.Session()
        # 记录响应时间
        self.res_times = []
        # 错误次数
        self.err_num = 0

    '''
    执行入口
    :param step_files 步骤配置文件或目录的列表
    '''
    def run(self, step_files):
        for path in step_files:
            # 1 模式文件
            if '*' in path:
                dir, pattern = path.rsplit(os.sep, 1)  # 从后面分割，分割为目录+模式
                if not os.path.exists(dir):
                    raise Exception(f'步骤配置目录不存在: {dir}')
                self.run_1dir(dir, pattern)
                return

            # 2 不存在
            if not os.path.exists(path):
                raise Exception(f'步骤配置文件或目录不存在: {path}')

            # 3 目录: 遍历执行子文件
            if os.path.isdir(path):
                self.run_1dir(path)
                return

            # 4 纯文件
            self.run_1file(path)

    # 执行单个步骤目录: 遍历执行子文件
    # :param path 目录
    # :param pattern 文件名模式
    def run_1dir(self, dir, pattern ='*.yml'):
        # 遍历目录: https://blog.csdn.net/allway2/article/details/124176562
        files = os.listdir(dir)
        files.sort() # 按文件名排序
        for file in files:
            if fnmatch.fnmatch(file, pattern): # 匹配文件名模式
                file = os.path.join(dir, file)
                if os.path.isfile(file):
                    self.run_1file(file)

    # 执行单个步骤文件
    # :param step_file 步骤配置文件路径
    # :param include 是否inlude动作触发
    def run_1file(self, step_file, include = False):
        # 获得步骤文件的绝对路径
        if include: # 补上绝对路径
            if not os.path.isabs(step_file):
                step_file = self.step_dir + os.sep + step_file
        else: # 记录目录
            step_file = os.path.abspath(step_file)
            self.step_dir = os.path.dirname(step_file)

        log.debug(f"加载并执行步骤文件: {step_file}")
        # 获得步骤
        steps = read_yaml(step_file)
        try:
            # 执行多个步骤
            self.run_steps(steps)
        except Exception as ex:
            log.debug(f"异常环境:当前步骤文件为 {step_file}, 当前请求url为 {self.curr_url}")
            raise ex

    # 执行多个步骤
    def run_steps(self, steps):
        # 逐个步骤调用多个动作
        for step in steps:
            for action, param in step.items():
                self.run_action(action, param)

    '''
    执行单个动作：就是调用动作名对应的函数
    :param action 动作名
    :param param 参数
    '''
    def run_action(self, action, param):
        if 'for(' in action:
            n = int(action[4:-1])
            self.do_for(param, n)
            return

        if 'concurrent(' in action:
            concurrency, req_num = action[11:-1].split(',')
            self.concurrent(param, int(concurrency), int(req_num))
            return

        if action not in self.actions:
            raise Exception(f'无效动作: [{action}]')

        # 调用动作对应的函数
        log.debug(f"处理动作: {action}={param}")
        func = self.actions[action]
        func(param)

    # --------- 动作处理的函数 --------
    # 并发测试
    # :param steps 每个迭代中要执行的步骤
    # :param concurrency 并发数
    # :param req_num 每个线程的请求数
    def concurrent(self, steps, concurrency = None, req_num = 1):
        if concurrency == None:
            raise Exception(f'并发动作必须指定并发数')

        log.debug(f"-- 开始 concurrent({concurrency},{req_num}) --")
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
                    log.debug(e)
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
        log.debug(f"-- 结束 concurrent({concurrency},{req_num}) --")
        log.debug("总耗时(秒): %s", cost_time)
        log.debug('响应次数: %s', n)
        log.debug('成功次数: %s', n - self.err_num)
        log.debug('错误次数: %s', self.err_num)
        log.debug('最大耗时(秒): %s', max(self.res_times))
        log.debug('最小耗时(秒): %s', min(self.res_times))
        log.debug('平均耗时(秒): %s', sum(self.res_times) / n)
        log.debug('吞吐量: %s', n / cost_time)

    # for循环
    # :param steps 每个迭代中要执行的步骤
    # :param n 循环次数
    def do_for(self, steps, n = None):
        label = f"for({n})"
        if n == None:
            n = sys.maxsize # 最大int，等于无限循环次数
            label = f"for(∞)"
        log.debug(f"-- 开始循环: {label} -- ")
        try:
            for i in range(n):
                # i+1表示迭代次数比较容易理解
                log.debug(f"第{i+1}次迭代")
                set_var('for_i', i+1)
                self.run_steps(steps)
        except BreakException as e:  # 跳出循环
            log.debug(f"-- 跳出循环: {label}, 跳出条件: {e.condition} -- ")
        else:
            log.debug(f"-- 终点循环: {label} -- ")

    # 执行一次子步骤，相当于 for(1)
    def once(self, steps):
        self.do_for(steps, 1)

    # 检查并继续for循环
    def moveon_if(self, expr):
        # break_if(条件取反)
        self.break_if(f"not ({expr})")

    # 跳出for循环
    def break_if(self, expr):
        val = eval(expr, globals(), bvars)  # 丢失本地与全局变量, 如引用不了json模块
        if bool(val):
            raise BreakException(expr)

    # 加载并执行其他步骤文件
    def include(self, step_file):
        self.run_1file(step_file, True)

    # 设置变量
    def set_vars(self, vars):
        for k, v in vars.items():
            v = replace_var(v)  # 替换变量
            set_var(k, v)

    # 打印变量
    def print_vars(self, _):
        log.info(f"打印变量: {bvars}")

    # 睡眠
    def sleep(self, seconds):
        seconds = replace_var(seconds)  # 替换变量
        if isinstance(self.session, HttpSession): # 如果是locust场景, 则挂起协程
            gevent.sleep(seconds)
        else:
            time.sleep(int(seconds))

    # 打印
    def print(self, msg):
        msg = replace_var(msg)  # 替换变量
        log.info(msg)

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

    # get请求
    # :param config {url, headers, data, validate_by_jsonpath, validate_by_css, validate_by_xpath, extract_by_jsonpath, extract_by_css, extract_by_xpath, extract_by_eval}
    def get(self, config = {}):
        url = self._get_url(config)
        data = self._get_data(config)
        headers = self._get_headers(config)
        res = self.session.get(url, headers=headers, data=data)
        # log.debug(res.text)
        # 解析响应
        self._analyze_response(res, config)

    # post请求
    # :param config {url, headers, data, validate_by_jsonpath, validate_by_css, validate_by_xpath, extract_by_jsonpath, extract_by_css, extract_by_xpath, extract_by_eval}
    def post(self, config = {}):
        url = self._get_url(config)
        data = self._get_data(config)
        headers = self._get_headers(config)
        res = self.session.post(url, headers=headers, data=data)
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
        res = self.session.post(url, headers=headers, files=files)
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
        res = self.session.get(url, headers=headers, data=data)

        # 保存响应的文件
        write_byte_file(save_file, res.content)
        # 设置变量
        set_var('download_file', save_file)
        self.downloaded_files[url] = save_file
        log.debug(f"下载文件: url为{url}, 另存为{save_file}")
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
            raise Exception('目录太多文件，建议新建目录')

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
        log.debug(f"识别验证码: 图片为{file_path}, 验证码为{captcha}")
        # 删除文件
        #os.remove(file)

# cli入口
def main():
    # 基于yaml的执行器
    boot = HttpBoot()
    # 步骤配置的yaml
    if len(sys.argv) > 1:
        step_files = sys.argv[1:]
    else:
        raise Exception("未指定步骤配置文件或目录")
    # 执行yaml配置的步骤
    boot.run(step_files)

if __name__ == '__main__':
    main()