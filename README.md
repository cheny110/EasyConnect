# EasyConnect
This program helps to accomplish school wifi verification! Specially designed for Zhengzhou University of Light Industry



You can test and modify the program to adapt to your wifi verifaction environment.

Development Environment:Linux Deepin,Pycharm .

email to chenyprivate@vip.qq.com for help

                                                
File tree:

    EasyConnect:    
                .gti : git relevant 
                .idea: pycharm project file
                 venv: python virtual environment files ,containing lib file necessary for build program.
                clean.sh:clean source code package,it removes all files after build 
                install.sh: give previllege to run to install program on you system
                unstall.sh:remove program from your system.
                main.py:main program entrance
                setup.py: install program with python
    
Way to install this program:
    I suggest you to install this program directly with install.sh in the following way:

       1.unzip source code package . 

       2.open your ternimal and cd to the directory of EasyConnect,which means your ternimal should under /PathtoContainSourcecode/EasyConnect/

       3.with pip already satisfied , run command "pip install -r requirements.txt --user" to get all required modules.
       
       4.in linux ,run "sudo bash install.sh " on ternimal,then innput your adminastor password to wait untill this process comlete.

       5.in windows, change pynotificator to pynotifactor[win] to support popup notify function. Or you can remove send_notify() function . 
          and you should pack the program by yourself if you'd like to do so.
    
Way to uninstall this program:
       please refer to the way to install this program to run uninstll.sh to remove this program from you system.
       

Illustration:
       function in the program may doesn't work in Windows system, you can relpace notifactor modules with notifactor[win] modules.
       run command "pip uninstall notifactor" ; "pip install notifactor[win]" You may run command with previledge rights and install pip                            first.
        when on Windows system , your should build this program with command "pyinstaller -F main.py -p "./EasyConnect/venv/lib/python3.7/site-packages" -i EasyConnect.ico" . Then cd to ./EasyConnect/dist ,if you build this program successfully,you should see an executive file,just put it in your favorite place then double click on it to run.


       main fuction in main.py helps you to connect to zzuli-teacher .you should fill your account in file teacher.json ,"DDDDD" refers to your name, and "upass" refers to your password.
       main function in student.py helps you to connect to zzuli-student . you should fill your account in file student.py. fill "DDDD"'s value like this ",0,541xxxxx@other" number before @ refers to your account, other refers to your service provider.
       "联通"=unicom,"单宽"=other, "移动" is not in trial list. you can try it yourself. Don't forget to fill your password .
                                                                       
                                                                                                                    

                                                                                                                         --by Cheny