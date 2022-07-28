我们在安装好 HttpBoot 后, 会生成 `LocustBoot` 命令, 该命令通过接收一个yaml文件参数来驱动 locust 做压测

## 使用
```
LocustBoot 任务配置文件.yml
```

## 任务配置文件及demo
用于指定 locust 任务, 示例见源码 [example/locust-jym-api.yml](https://github.com/shigebeyond/HttpBoot/tree/main/example/locust-jym-api.yml);

顶级的元素是任务, 实际上对应的是 locust 用户类中的方法(on_start/on_stop/task);

每个任务下包含的是 HttpBoot 的步骤, 简单的说就是在 HttpBoot 步骤上多包了一层 locust 的操作 

## 配置详解
支持通过yaml来配置 locust 任务;

```yaml
# 1 基础url
base_url: http://api.jym0.com/
# 2 压测开始前置处理
on_start:
  # 可包含 HttpBoot 的步骤
  - print: 开始
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