#!/usr/bin/env python
# -*-coding:utf-8-*-

# Edit by ZeroC
# 20180807

import socket
import datetime
import time
import os
import sys
import json
import tarfile
import smtplib
from email.header import Header
from email.mime.text import MIMEText


# 发送信息，邮件
class Sendmessage:
    def __init__(self, subject=u'Nginx日志切割异常报警'):
        self.subject = subject

    def send_mail(self, smtpserver, port, sender, reciver, password, message):
        msg = MIMEText(message)
        msg["From"] = sender
        msg["To"] = reciver
        msg["Subject"] = Header(self.subject, "utf-8").encode()

        try:
            server = smtplib.SMTP_SSL(smtpserver, port)
            server.login(sender, password)
            server.sendmail(msg["From"], msg["To"], msg.as_string())
            server.quit()
        except Exception as e:
            print(u"%s, Error:发送失败！" % e)

    def send_dingding(self, tokenid, message):
        url = "https://oapi.dingtalk.com/robot/send?access_token=" + tokenid
        header = {
            "Content-Type": "application/json",
            "charset": "utf-8"
        }
        # 接口文档https://open-doc.dingtalk.com/docs/doc.htm?spm=a219a.7629140.0.0.karFPe&treeId=257&articleId=105735&docType=1
        data = {
            "msgtype": "text",
            "text": {
                "content": message
            },
        }

        sendData = json.dumps(data, indent=4)
        if check_python():
            import urllib.request as ul
        else:
            import urllib2 as ul

        request = ul.Request(url=url, data=sendData, headers=header)
        urlopen = ul.urlopen(request)
        return urlopen.read


# Python版本
def check_python():
    if sys.version_info > (3, 0):
        return 1
    else:
        return 0


# 检查nginx状态
def check_nginx(nginx_sbin, nginx_conf):
    if not check_python():
        import commands as com
    else:
        import subprocess as com
    output = com.getstatusoutput("%s -t -c %s" % (nginx_sbin, nginx_conf))
    return output


# 重启nginx
def reload_nginx(nginx_sbin, nginx_conf):
    pid = os.system("ps aux | grep nginx| grep -v grep| awk '{print $2}'")
    if pid:
        os.system("%s -s reload" % nginx_sbin)
    else:
        os.system("%s -c %s" % (nginx_sbin, nginx_conf))


# 日志重命名
def rename_log(log, flag):
    """???log??
	access.log --> access-20180815.log
    """
    if os.path.exists(log):
        os.system("mv %s %s-%s.%s" % (log, log.split('.')[0], flag, log.split('.')[1]))
        return 0
    else:
        return 1


# 存储所有日志
def get_files(path):
    """所有日志存储在files列表中"""
    files = []
    for dirpath, dirname, filename in os.walk(path):
        for p in dirname:
            files.append(os.path.join(dirpath, p))
        for f in filename:
            files.append(os.path.join(dirpath, f))
    return files


# 日志修改时间
def get_mtime(log):
    mtime_stamp = os.path.getmtime(log)
    local_time = time.localtime(mtime_stamp)
    mtime = time.strftime('%Y-%m-%d', local_time)
    return mtime


# 备份日志
def package_log(log):
    tar = tarfile.open('%s.tar.gz' % log, 'w:gz')
    tar.add(log)
    tar.close()


if __name__ == "__main__":
    """"""
    # IP地址
    IP = socket.gethostbyname(socket.gethostname())

    # 发送信息
    MESSAGE = {'Nginx-Error':[], 'Log-Warn':[], 'Other':[]}

    # 初始化Sendmessage类
    Message = Sendmessage()

    # Today
    TODAY = datetime.datetime.now().strftime("%Y-%m-%d")
    # 7 days ago
    WEEKAGO = (datetime.datetime.now() - datetime.timedelta(days=7)).strftime("%Y-%m-%d")

    # 读取配置文件
    f = 'conf.ini'
    if check_python():
        import configparser as cf
    else:
        import ConfigParser as cf
    config = cf.ConfigParser()
    config.read(f)

    NGINX = config.get('nginx', 'sbin')
    CONF = config.get('nginx', 'conf')
    EXT = config.get('nginx', 'ext')
    # Log
    LOG = []
    for lopts in config.options('nginx-log'):
        LOG.append(config.get('nginx-log', lopts))

    # 判断nginx配置文件是否正常
    if check_nginx(NGINX, CONF)[0]:
        # Nginx配置错误提示
        MESSAGE['Nginx-Error'].append(check_nginx(NGINX, CONF)[1])
    else:
        for logs in LOG:
            logfiles = get_files(logs)
            for logf in logfiles:
                if os.path.isfile(logf):
                    logpath = os.path.split(logf)[0]
                    logname = os.path.split(logf)[1]
                    # 切换工作目录
                    os.chdir(logpath)
                    # 切割当天日志
                    newfile = logname.split('.')[0] + '.%s' % TODAY
                    if logname == newfile:
                        if get_mtime(logname) is TODAY:
                            rename_log(logname, TODAY)
                    # ??7????
                    oldfile = logname.split('-')[0] + '-%s.%s' % (WEEKAGO, EXT)
                    if logname == oldfile:
                        package_log(logname)
                    else:
                        MESSAGE['Log-Warn'].append('%s/%s not exists !' % (logpath, oldfile))
        # ??nginx
        reload_nginx(NGINX, CONF)

    msg = {}
    for mk in MESSAGE:
        if MESSAGE[mk]:
            msg[mk] = MESSAGE[mk]
    if msg:
        # 发送钉钉信息
        if config.getboolean('dingding', 'flag'):
            Token = config.get('dingding', 'token')
            Message.send_dingding(Token, msg)

        # 发送邮件
        if config.getboolean('mail', 'flag'):
            # 邮件发送人
            SENDER = config.get('mail', 'sender')

            # 邮箱客户端授权密码
            PASSWORD = config.get('mail', 'password')

            # 邮件接收人
            RECIVER = []
            for mopts in config.options('mail-reciver'):
                RECIVER.append(config.get('mail-reciver', mopts))

            # 邮箱SMTP服务器
            SERVER = config.get('mail', 'server')

            if config.getboolean('mail', 'ssl'):
                PORT = config.getint('mail-ssl', 'port')
            else:
                PORT = config.getint('mail-nossl', 'port')

            Message.send_mail(smtpserver=SERVER, port=PORT, sender=SENDER, reciver=RECIVER, password=PASSWORD, message=json.dumps(msg))
