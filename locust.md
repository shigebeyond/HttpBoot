我们在安装好 HttpBoot 后, 会生成 `LocustBoot` 命令, 该命令通过接收一个yaml文件参数来驱动 locust 做压测；

优先使用协程来压测，以便提高并发能力，如果你的系统不支持 gevent，则使用线程来压测。

## 使用
```
LocustBoot 任务配置文件.yml
LocustBoot 任务配置文件.yml 后面还可以通过-l来指定locust命令的其他参数, 如 -l "--headless -u 10 -r 5 -t 20s"
```

如执行`LocustBoot example/locust-jym-api.yml`， 会启动web服务， 你可访问 http://localhost:8089/，来操作locust服务；
其日志输出如下
```
/usr/local/lib/python3.7/dist-packages/locust/__init__.py:11: MonkeyPatchWarning: Monkey-patching ssl after ssl has already been imported may lead to errors, including RecursionError on Python 3.6. It may also silently lead to incorrect behaviour on Python 3.7. Please monkey-patch earlier. See https://github.com/gevent/gevent/issues/1016. Modules that had direct imports (NOT patched): ['urllib3.util (/home/shi/.local/lib/python3.7/site-packages/urllib3/util/__init__.py)', 'urllib3.util.ssl_ (/home/shi/.local/lib/python3.7/site-packages/urllib3/util/ssl_.py)']. 
  monkey.patch_all()
locust -f /home/shi/.local/lib/python3.7/site-packages/HttpBoot/locust_boot.py -b example/locust-jym-api.yml
[2022-07-29 11:08:32,414] shi-PC/INFO/locust.main: Starting web interface at http://0.0.0.0:8089 (accepting connections from all network interfaces)
[2022-07-29 11:08:32,423] shi-PC/INFO/locust.main: Starting Locust 2.10.1
```

如执行`LocustBoot example/locust-jym-api.yml -l "--headless -u 10 -r 5 -t 20s --csv=result --html=report.html"`， 会自动执行压测脚本，并生成报告，报告文件如下：
```
report.html
result_exceptions.csv
result_failures.csv
result_stats.csv
result_stats_history.csv
```

## 任务配置文件及demo
用于指定 locust 任务, 示例见源码 [example/locust-jym-api.yml](https://github.com/shigebeyond/HttpBoot/tree/main/example/locust-jym-api.yml);

顶级的元素是任务, 实际上对应的是 locust 用户类中的方法(on_start/on_stop/task);

每个任务下包含的是 HttpBoot 的步骤, 简单的说就是在 HttpBoot 步骤上多包了一层 locust 的操作 

[演示视频](https://www.zhihu.com/zvideo/1573006826647560194)

## 配置详解
支持通过yaml来配置 locust 任务;

```yaml
# 1 基础url
base_url: http://api.jym0.com/
# 2 压测开始前置处理
on_start:
  # 可包含 HttpBoot 的步骤
  - print: 开始
    log_level: error # 如果怕日志太多，则关掉调试日志
# 3 压测过程中要执行的任务
task:
  # 可包含 HttpBoot 的步骤
  # 发get请求
  - get:
      url: home/ # url, 实际url会在前面拼接 base_url
    sleep: 2
  # 发post请求
  - post:
      url: home/get_bank_list # url, 实际url会在前面拼接 base_url
# 4 压测结束后置处理
on_stop:
  # 可包含 HttpBoot 的步骤
  - print: 结束
```