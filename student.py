import requests
import socket
import uuid
import datetime
import pynotificator
from main import send_notify,get_mac,getip,load_data,headers
import json


def login_student():
    signin_url='http://10.168.6.10:801/eportal/?c=ACSetting&a=Login&protocol=http:&hostname=10.168.6.10&iTermType=1&wlanuserip='+ip+'&wlanacip=10.168.6.9&mac=00-00-00-00-00-00&ip='+ip+'&enAdvert=0&queryACIP=0&loginMethod=1'
    headers={
    'Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Encoding':'gzip,deflate',
    'Accept-Language':'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
    'Connection':'keep-alive',
    'Content-Length':'152',
    'Content-Type':'application/x-www-form-urlencoded',
    'Cookie':'program=new;vlan=0;ip=10.67.24.132;ssid=null;areaID=null;md5_login2=%2C0%2C1998004%7C123123; PHPSESSID=f2fp2ubgiem23r9kttrpe0cjl0',
    'Host':'10.168.6.10:801',
    'Origin':'http://10.168.6.10',
    'Referer':'http://10.168.6.10/a70.htm?wlanuserip=10.67.24.132&wlanacip=10.168.6.9&wlanacname=&vlanid=0&ip=10.67.24.132&ssid=null&areaID=null&mac=00-00-00-00-00-00',
    'Upgrade-Insecure-Requests':'1',
    'User-Agent':'Mozilla/5.0 (X11; Linux x86_64; rv:78.0) Gecko/20100101 Firefox/78.0'
    }
    sub_json=load_data('student_config.json')
    resp=requests.post('http://10.168.6.10:801/eportal/?c=ACSetting&a=Login&protocol=http:&hostname=10.168.6.10&iTermType=1&wlanuserip='+ip+'&wlanacip=10.168.6.9&mac=00-00-00-00-00-00&ip='+ip+'&enAdvert=0&queryACIP=0&loginMethod=1',sub_json,headers)
    #print(resp.status_code)
    return resp.status_code


        


if __name__=='__main__':
    ip=getip()
    mac=get_mac()
    status=login_student()
    if status is 200:
        send_notify("连接成功")
    else:
        send_notify("连接失败,请重新尝试")
    


