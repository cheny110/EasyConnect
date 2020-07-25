#!bash bin
#说明:自动安装脚本
#作者：cheny
#在运行此脚本前建议阅读readme
echo"正在打包程序..."
pyinstaller -F main.py -p ./venv/lib/python3.7/site-packages
echo "正在移动文件..."
sudo mkdir /opt/apps/easyconnect
sudo cp ./dist/main /opt/apps/easyconnect/easyconnect
sudo cp EasyConnect.ico /opt/apps/easyconnect
sudo chmod 777 /opt/apps/easyconnect/easyconnect
sudo cp easyconnect.desktop /usr/share/applications/easyconnect.desktop
echo "安装完成"

