import requests
import socket
import uuid
import datetime
mac_list=['a0c589865439','502b73d42c7a']
expire_time=[2020,8,31]
def check_time():
    i = datetime.datetime.now()
    if i.year==expire_time[0] and i.month<=expire_time[1] and i.day<=expire_time[2]:
        pass
    else :
        print("program expired,connected failed")
        exit()
def get_mac():
    node = uuid.getnode()
    mac=uuid.UUID(int=node).hex[-12:]
    return mac

def getip():
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
    usr_name=',0,1998004'
    usr_pwd='123123'
    ip=getip()
    mac=get_mac()
    #check_time()
    if mac in mac_list:
        print("MAC Address Right!")
    else:
        print("MAC Address fault! Connected failed")
        exit()

    form_content={
        'DDDDD':usr_name,
        'upass':usr_pwd,
        'R1':'0',
        'R2':'0',
        'R3': '0',
        'R6':'0',
        'para':'00',
        '0MKKey':'123456',
        'buttonClicked':'',
        'redirect_url':'',
        'err_flag':'',
        'username':'',
        'password':'',
        'user':'',
        'cmd':'',
        'loggin':''
    }
    signin_url="http://10.168.6.10/a70.htm?wlanuserip="+ip+\
               "&wlanacip=10.168.6.9&wlanacname=&vlanid=0&ip="+ip+\
               "&ssid=null&areaID=null&mac=00-00-00-00-00-00"
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

    resp=requests.get(signin_url,headers)
    resp.encoding = resp.apparent_encoding
    #print(resp.text)
    resp=requests.post('http://10.168.6.10:801/eportal/?c=ACSetting&a=Login&protocol=http:&hostname=10.168.6.10&iTermType=1&wlanuserip='+ip+'&wlanacip=10.168.6.9&mac=00-00-00-00-00-00&ip='+ip+'&enAdvert=0&queryACIP=0&loginMethod=1',form_content,headers)
    resp.encoding=resp.apparent_encoding
    print("Connected successfully!")

if __name__=='__main__':
    loggin()