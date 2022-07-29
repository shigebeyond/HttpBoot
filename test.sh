#!/bin/sh
cd `dirname $0`

# 测试 HttpBoot
HttpBoot example/jym-api.yml
HttpBoot example/jym-pc.yml

# 测试 LocustBoot
LocustBoot example/locust-jym-api.yml