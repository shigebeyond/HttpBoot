[GitHub](https://github.com/shigebeyond/HttpBoot) | [Gitee](https://gitee.com/shigebeyond/HttpBoot)

# HttpBoot - yaml驱动http接口自动化测试+性能测试

## 概述
一般测试http接口，要写python代码；

考虑到部分测试伙伴python能力不足，因此实现HttpBoot，支持通过yaml配置测试步骤;

框架通过编写简单的yaml, 就可以执行一系列复杂的http请求操作步骤, 如get/post/下载图片/校验响应/提取变量/打印变量等，极大的简化了伙伴编写自动化测试脚本的工作量与工作难度，大幅提高人效；

框架通过提供类似python`for`/`if`/`break`语义的步骤动作，赋予伙伴极大的开发能力与灵活性，能适用于广泛的测试场景。

框架提供`include`机制，用来加载并执行其他的步骤yaml，一方面是功能解耦，方便分工，一方面是功能复用，提高效率与质量，从而推进测试整体的工程化。

## 特性
1. 支持通过yaml来配置执行的步骤，简化了自动化测试开发:
每个步骤可以有多个动作，但单个步骤中动作名不能相同（yaml语法要求）;
动作代表一种http请求操作，如get/post/upload等等;
2. 支持提取器
3. 支持校验器
4. 支持识别验证码(使用有道ocr)
5. 支持类似python`for`/`if`/`break`语义的步骤动作，灵活适应各种场景
6. 支持`include`引用其他的yaml配置文件，以便解耦与复用
7. 支持用多线程来并发测试
8. 整合locust来做压力测试

## todo
1. 支持更多的动作

## 安装
```
pip3 install HttpBoot
```

安装后会生成命令`HttpBoot`;

注： 对于深度deepin-linux系统，生成的命令放在目录`~/.local/bin`，建议将该目录添加到环境变量`PATH`中，如
```
export PATH="$PATH:/home/shi/.local/bin"
```

## 整合locust
参考[整合locust](locust.md)

## 使用
```
# 1 执行单个文件
HttpBoot 步骤配置文件.yml

# 2 执行多个文件
HttpBoot 步骤配置文件1.yml 步骤配置文件2.yml ...

# 3 执行单个目录, 即执行该目录下所有的yml文件
HttpBoot 步骤配置目录

# 4 执行单个目录下的指定模式的文件
HttpBoot 步骤配置目录/step-*.yml
```

如执行 `HttpBoot example/jym-api.yml`，输出如下
```
/usr/local/lib/python3.7/dist-packages/locust/__init__.py:11: MonkeyPatchWarning: Monkey-patching ssl after ssl has already been imported may lead to errors, including RecursionError on Python 3.6. It may also silently lead to incorrect behaviour on Python 3.7. Please monkey-patch earlier. See https://github.com/gevent/gevent/issues/1016. Modules that had direct imports (NOT patched): ['urllib3.util (/home/shi/.local/lib/python3.7/site-packages/urllib3/util/__init__.py)', 'urllib3.util.ssl_ (/home/shi/.local/lib/python3.7/site-packages/urllib3/util/ssl_.py)']. 
  monkey.patch_all()
加载并执行步骤文件: /ohome/shi/code/python/HttpBoot/example/jym-api.yml
处理动作: base_url=http://api.jym0.com/
处理动作: get={'url': 'home/'}
发送请求：curl -X GET -H 'Accept: */*' -H 'Accept-Encoding: gzip, deflate, br' -H 'Connection: keep-alive' -H 'User-Agent: python-requests/2.27.1' http://api.jym0.com/home/
处理动作: post={'url': 'home/get_bank_list', 'data': {'client_type': 3, 'unique_code': 'FA95024A-EC83-46A3-AEE0-3D180795767E', 'app_version': 1.0, 'v': '${random_int(6)}'}, 'extract_by_jsonpath': {'code': ode'}, 'validate_by_jsonpath': {'$.code': {'=': 200}, '$.msg': {'contains': '成功'}}}
发送请求：curl -X POST -H 'Accept: */*' -H 'Accept-Encoding: gzip, deflate, br' -H 'Connection: keep-alive' -H 'Content-Length: 87' -H 'Content-Type: application/x-www-form-urlencoded' -H 'Cookie: ci_sessifgns2l8q0r8f8s0ntbrg96th0aar7m' -H 'User-Agent: python-requests/2.27.1' -d 'client_type=3&unique_code=FA95024A-EC83-46A3-AEE0-3D180795767E&app_version=1.0&v=154262' http://api.jym0.com/home/get_bank_list
处理校验函数: ==200
处理校验函数: contains=成功
从响应中抽取参数: code=200
```

## 步骤配置文件及demo
用于指定多个步骤, 示例见源码 [example](https://github.com/shigebeyond/HttpBoot/tree/main/example) 目录下的文件;

顶级的元素是步骤;

每个步骤里有多个动作(如sleep)，如果动作有重名，就另外新开一个步骤写动作，这是由yaml语法限制导致的，但不影响步骤执行。

## 配置详解
支持通过yaml来配置执行的步骤;

每个步骤可以有多个动作，但单个步骤中动作名不能相同（yaml语法要求）;

动作代表一种http请求，如get/post/upload等

下面详细介绍每个动作:

1. sleep: 线程睡眠; 
```yaml
sleep: 2 # 线程睡眠2秒
```

2. print: 打印, 支持输出变量/函数; 
```yaml
# 调试打印
print: "总申请数=${dyn_data.total_apply}, 剩余份数=${dyn_data.quantity_remain}"
```

变量格式:
```
$msg 一级变量, 以$为前缀
${data.msg} 多级变量, 用 ${ 与 } 包含
```

函数格式:
```
${random_str(6)} 支持调用函数，目前仅支持3个函数: random_str/random_int/incr
```

函数罗列:
```
random_str(n): 随机字符串，参数n是字符个数
random_int(n): 随机数字，参数n是数字个数
incr(key): 自增值，从1开始，参数key表示不同的自增值，不同key会独立自增
```


3. base_url: 设置基础url
```yaml
base_url: https://www.taobao.com/
```

4. common_data: 设置公共请求参数;
如果是get请求, 则挂在query参数, 否则挂在post参数中
```yaml
common_data:
    uid: 1
```

5. common_headers: 设置公共请求头
```yaml
common_headers:
    uid: 1
```

6. get: 发get请求; 
```yaml
get:
    url: $dyn_data_url # url,支持写变量
    extract_by_eval:
      dyn_data: "json.loads(response.text[16:-1])" # 变量response是响应对象
```

7. post: 发post请求; 
```yaml
post:
    url: http://admin.jym1.com/store/add_store # url,支持写变量
    is_ajax: true
    data: # post的参数
      # 参数名:参数值
      store_name: teststore-${random_str(6)}
      store_logo_url: '$img'
```

8. upload: 上传文件; 
```yaml
upload: # 上传文件/图片
    url: http://admin.jym1.com/upload/common_upload_img/store_img
    files: # 上传的多个文件
      # 参数名:文件本地路径
      file: /home/shi/fruit.jpeg
    extract_by_jsonpath:
      img: $.data.url
```

9. download: 下载文件; 
变量`download_file`记录最新下载的单个文件
```yaml
download:
    url: https://img.alicdn.com/tfscom/TB1t84NPuL2gK0jSZPhXXahvXXa.jpg_q90.jpg
    save_dir: downloads # 保存的目录，默认为 downloads
    save_file: test.jpg # 保存的文件名，默认为url中最后一级的文件名
```

10. recognize_captcha: 识别验证码; 
参数同 `download` 动作， 因为内部就是调用 `download`;
而变量`captcha`记录识别出来的验证码
```
recognize_captcha:
    url: http://admin.jym1.com/login/verify_image
    # save_dir: downloads # 保存的目录，默认为 downloads
    # save_file: test.jpg # 保存的文件名，默认为url中最后一级的文件名
```

11. for: 循环; 
for动作下包含一系列子步骤，表示循环执行这系列子步骤；变量`for_i`记录是第几次迭代（从1开始）
```yaml
# 循环3次
for(3) :
  # 每次迭代要执行的子步骤
  - get:
      url: https://www.baidu.com
    sleep: 2

# 无限循环，直到遇到跳出动作
# 有变量for_i记录是第几次迭代（从1开始）
for:
  # 每次迭代要执行的子步骤
  - break_if: for_i>2 # 满足条件则跳出循环
    get:
      url: https://www.baidu.com
    sleep: 2
```

12. once: 只执行一次，等价于 `for(1)`; 
once 结合 moveon_if，可以模拟 python 的 `if` 语法效果
```yaml
once:
  # 每次迭代要执行的子步骤
  - moveon_if: for_i<=2 # 满足条件则往下走，否则跳出循环
    get:
      url: https://www.baidu.com
    sleep: 2
```

13. break_if: 满足条件则跳出循环; 
只能定义在for循环的子步骤中
```yaml
break_if: for_i>2 # 条件表达式，python语法
```

14. moveon_if: 满足条件则往下走，否则跳出循环; 
只能定义在for循环的子步骤中
```yaml
moveon_if: for_i<=2 # 条件表达式，python语法
```

15. 并发处理 
```yaml
concurrent(5,10): # 并发线程数为5, 每线程处理请求数据为10
  # 每次迭代要执行的子步骤
  - get:
      url: https://www.baidu.com
```

16. include: 包含其他步骤文件，如记录公共的步骤，或记录配置数据(如用户名密码); 
```yaml
include: part-common.yml
```

17. set_vars: 设置变量; 
```yaml
set_vars:
  name: shi
  password: 123456
  birthday: 5-27
```

18. print_vars: 打印所有变量; 
```yaml
print_vars:
```

## 校验器
只针对 get/post/upload 有发送http请求的动作, 主要是为了校验响应的内容

1. validate_by_xpath: 
从html的响应中解析 xpath 路径对应的元素的值
```yaml
validate_by_xpath:
  "//div[@id='goods_id']": # 元素的xpath路径
    '>': 0 # 校验符号或函数: 校验的值, 即 id 元素的值>0
  "//div[@id='goods_title']":
    contains: 衬衫 # 即 title 元素的值包含'衬衫'
```

2. validate_by_css: 
从html的响应中解析 css selector 模式对应的元素的值
```yaml
validate_by_css:
  '#id': # 元素的css selector 模式
    '>': 0 # 校验符号或函数: 校验的值, 即 id 元素的值>0
  '#goods_title':
    contains: 衬衫 # 即 title 元素的值包含'衬衫'
```

3. validate_by_jsonpath: 
从json响应中解析 多层属性 的值
```yaml
validate_by_jsonpath:
  '$.data.goods_id':
     '>': 0 # 校验符号或函数: 校验的值, 即 id 元素的值>0
  '$.data.goods_title':
    contains: 衬衫 # 即 title 元素的值包含'衬衫'
```

#### 校验符号或函数
1. `=`: 相同
2. `>`: 大于
3. `<`: 小于
4. `>=`: 大于等于
5. `<=`: 小于等于
6. `contains`: 包含子串
7. `startswith`: 以子串开头
8. `endswith`: 以子串结尾
9. `regex_match`: 正则匹配

## 提取器
只针对 get/post/upload 有发送http请求的动作, 主要是为了从响应中提取变量

1. extract_by_xpath:
从html的响应中解析 xpath 路径指定的元素的值
```yaml
extract_by_xpath:
  # 变量名: xpath路径
  goods_id: //table/tbody/tr[1]/td[1] # 第一行第一列
```

2. extract_by_css:
从html的响应中解析 css selector 模式指定的元素的值
```yaml
extract_by_css:
  # 变量名: css selector 模式
  goods_id: table>tbody>tr:nth-child(1)>td:nth-child(1) # 第一行第一列
```

3. extract_by_jsonpath:
从json响应中解析 多层属性 的值
```yaml
extract_by_jsonpath:
  # 变量名: json响应的多层属性
  img: $.data.url
```

4. extract_by_eval:
使用 `eval(表达式)` 执行表达式, 并将执行结果记录到变量中
```yaml
extract_by_eval:
    # 变量名: 表达式（python语法）
    dyn_data: "json.loads(response.text[16:-1])" # 变量response是响应对象
```