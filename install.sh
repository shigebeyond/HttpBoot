#!/bin/sh
echo '卸载'
pip3 uninstall HttpBoot -y
echo '打包'
python3 setup.py sdist bdist_wheel
echo '安装到本地'
pip3 install dist/*.whl