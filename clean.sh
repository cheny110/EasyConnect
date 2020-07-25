#! bash bin
#clean source code package
#author:cheny
echo "cleaning files"
sudo rm ./build -r
sudo rm  ./dist -r
sudo rm __pycache__ -r
sudo rm main.spec 
echo "clean finished!"
