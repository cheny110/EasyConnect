from setuptools import setup,find_packages

setup(
    name='EasyConnectTool',
    version='1.0.2',
    keywords=(" Connect School Wifi"),
    long_description="A tool to connect school wifi and auto authentication!",
    license="GNU License",
    url="https://github.com/cheny110/EasyConnect",
    author='cheny',
    author_email="chenyprivate@vip.qq.com",
    packages=find_packages(),
    include_package_data=True,
    platforms="linux",
    scripts=['main.py'],
    install_requires=[],




)