import yaml
import json
from pyutilb.file import *

# 读 hrun json 文件
json_file = 'hrun.json'
data = read_file(json_file)
data = data.replace('"', '\\"') # "转\"
data = data.replace("'", '"') # '转"
data = json.loads(data)
# hrun请求
req1 = data['test']['request']
# 转 httpboot请求
req2 = {
  req1['method']: {
    'url': req1['url'],
    'data': req1['data']
  }
}
# 存为 yaml
data = yaml.dump([req2])
print(data)
# write_file('httpboot.yml', data)