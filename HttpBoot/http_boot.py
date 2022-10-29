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
from pyutilb import log, ocr_youdao
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
            'exec': self.exec,
        }
        set_var('boot', self)
        # 当前文件
        self.step_file = None
        # 当前url
        self.curr_url = None
        # 当前session
        self.session = requests.Session()
        # 记录响应时间
        self.res_times = []
        # 错误次数
        self.err_num = 0
        # http动作的标签
        self.http_action_tags = {}

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
                    raise Exception(f'Step config directory not exist: {dir}')
                self.run_1dir(dir, pattern)
                return

            # 2 不存在
            if not os.path.exists(path):
                raise Exception(f'Step config file or directory not exist: {path}')

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
    def run_1file(self, step_file, include=False):
        # 加载步骤文件
        step_file, steps = self.load_1file(step_file, include)
        log.debug(f"Load and run step file: {step_file}")
        self.step_file = step_file
        # 先打标签
        self.tag_http_actions(steps)
        # 执行多个步骤
        self.run_steps(steps)
        # 清理标签
        self.http_action_tags.clear()

    # 加载单个步骤文件
    def load_1file(self, step_file, include):
        # 获得步骤文件的绝对路径
        if include:  # 补上绝对路径
            if not os.path.isabs(step_file):
                step_file = self.step_dir + os.sep + step_file
        else:  # 记录目录
            step_file = os.path.abspath(step_file)
            self.step_dir = os.path.dirname(step_file)
        # 获得步骤
        steps = read_yaml(step_file)
        return step_file, steps

    # 给所有http动作打标签
    def tag_http_actions(self, steps):
        # 逐个步骤检查多个动作
        for step in steps:
            for action, param in step.items():
                # http动作: 打标签
                if self.is_http_action(action):
                    self.tag_http_action(action, param)
                # include动作: 递归
                if action == 'include':
                    step_file, steps = self.load_1file(param, True)
                    # 递归打标签
                    self.tag_request_step(steps)

    # 是否是http动作
    def is_http_action(self, action):
        return action in ('get', 'post', 'upload', 'download')

    # 给单个http动作打标签
    def tag_http_action(self, action, config):
        # 指定标签
        if 'tag' in config and config['tag'] != None: # 有指定标签
            tags = (config['tag'])
        else: # 默认标签
            tag1 = f"{action} {config['url']}"
            tag2 = config['url']
            tags = (tag1, tag2)
        # 记录标签
        for tag in tags:
            tag = tag.rstrip('/') # 去掉最后的/
            self.http_action_tags[tag] = (action, config)

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
            n = self.parse_for_n(action)
            self.do_for(param, n)
            return

        if 'concurrent(' in action:
            concurrency, req_num = action[11:-1].split(',')
            self.concurrent(param, int(concurrency), int(req_num))
            return

        if action not in self.actions:
            raise Exception(f'Invalid action: [{action}]')

        # 先执行依赖的动作
        if self.is_http_action(action):
            self.run_dep_actions(param)

        # 调用动作对应的函数
        log.debug(f"handle action: {action}={param}")
        func = self.actions[action]
        func(param)

    # 执行依赖的动作
    def run_dep_actions(self, config):
        # 依赖的动作标签
        if 'deps' not in config or config['deps'] == None:
            return
        dep_action_tags = config['deps']
        if not isinstance(dep_action_tags, list):
            dep_action_tags = dep_action_tags.split(',')
        # 逐个调用依赖的动作
        for tag in dep_action_tags:
            tag = tag.rstrip('/') # 去掉最后的/
            if tag in self.http_action_tags:
                action, param = self.http_action_tags[tag]
                self.run_action(action, param)

    # --------- 动作处理的函数 --------
    # 并发测试
    # :param steps 每个迭代中要执行的步骤
    # :param concurrency 并发数
    # :param req_num 每个线程的请求数
    def concurrent(self, steps, concurrency = None, req_num = 1):
        if concurrency == None:
            raise Exception(f'Miss concurrency parameter')

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

    # 解析动作名中的for(n)中的n
    def parse_for_n(self, action):
        n = action[4:-1]
        # 1 数字
        if n.isdigit():
            return int(n)

        # 2 变量名, 必须是list类型
        n = get_var(n, False)
        if n == None or not (isinstance(n, list) or isinstance(n, int)):
            raise Exception(f'Variable in for({n}) parentheses must be int or list type')
        return n

    # for循环
    # :param steps 每个迭代中要执行的步骤
    # :param n 循环次数/循环的列表
    def do_for(self, steps, n = None):
        label = f"for({n})"
        # 循环次数
        if n == None:
            n = sys.maxsize # 最大int，等于无限循环次数
            label = f"for(∞)"
        # 循环的列表值
        items = None
        if isinstance(n, list):
            items = n
            n = len(items)
        log.debug(f"-- For loop start: {label} -- ")
        last_i = get_var('for_i', False) # 旧的索引
        last_v = get_var('for_v', False) # 旧的元素
        try:
            for i in range(n):
                # i+1表示迭代次数比较容易理解
                log.debug(f"{i+1}th iteration")
                set_var('for_i', i+1) # 更新索引
                if items == None:
                    v = None
                else:
                    v = items[i]
                set_var('for_v', v) # 更新元素
                self.run_steps(steps)
        except BreakException as e:  # 跳出循环
            log.debug(f"-- For loop break: {label}, break condition: {e.condition} -- ")
        else:
            log.debug(f"-- For loop finish: {label} -- ")
        finally:
            set_var('for_i', last_i) # 恢复索引
            set_var('for_v', last_v) # 恢复元素

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
        log.info(f"Variables: {bvars}")

    # 睡眠
    def sleep(self, seconds):
        seconds = replace_var(seconds)  # 替换变量
        if hasattr(os, 'posix_spawnp') and isinstance(self.session, HttpSession): # 如果是locust场景, 则挂起协程
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

    # 执行命令
    def exec(self, cmd):
        output = os.popen(cmd).read()
        log.debug(f"execute commmand: {cmd} | result: {output}")

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