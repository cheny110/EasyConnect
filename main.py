import requests
import socket
import uuid
import datetime
import pynotificator
import json

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


def send_notify(msg):
    '''
    This program send notification to desktop users! It only works in linux platform.
    If you want this function on windows platform, change pynotificator to punotificator[win] manually.
    :param msg:Nitofication message string you want to send .
    :return:None
    '''
    notify_box=pynotificator.DesktopNotification(msg,'EasyConnect','Waring',icon='network-wireless')
    notify_box.notify()



def get_mac():
    '''
    get mac address to specify computer
    '''
    node = uuid.getnode()
    mac=uuid.UUID(int=node).hex[-12:]
    #logger("get mac once,ID:"+mac)
    return mac

def getip():

    '''get internet ip'''
    try:
        s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        s.connect(('8.8.8.8',80))
        ip=s.getsockname()[0]
    finally:
        s.close()
    print(ip)
    return ip

    pass

def loggin():
    "log in to school wifi zzuli-teacher"
   
    #check whether application expired

    ip=getip()
    mac=get_mac()
    #submit form content
    sub_json=load_data('teacher_config.json')
    #url address
    signin_url='http://10.168.6.10:801/eportal/?c=ACSetting&a=Login&protocol=http:&hostname=10.168.6.10&iTermType=1&wlanuserip='+ip+'&wlanacip=10.168.6.9&mac=00-00-00-00-00-00&ip='+ip+'&enAdvert=0&queryACIP=0&loginMethod=1'
   

    #handle response
    resp=requests.get(signin_url,headers)
    resp.encoding = resp.apparent_encoding
    resp=requests.post(signin_url,sub_json,headers)
    return  resp.status_code


def logger(log):
    '''
    简单日志记录
    '''
    file_obj = open('easy_connect_log.txt','a+')
    now = datetime.datetime.now()
    file_obj.write(now.strftime('%Y-%m-%d %H:%M:%S:'))
    file_obj.write(log+'\n')
    file_obj.close()

def load_data(file):
    with open(file) as f:
        sub_json=json.load(f)
        f.close()
    
    return sub_json


# program entrance
if __name__=='__main__':
    loggin()