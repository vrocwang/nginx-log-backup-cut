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

if sys.version_info > (3, 0):
    import urllib.request as ul
    import subprocess as com
    import configparser as cf
else:
    import urllib2 as ul
    import commands as com
    import ConfigParser as cf


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

        request = ul.Request(url=url, data=sendData, headers=header)
        urlopen = ul.urlopen(request)
        return urlopen.read


# 检查nginx配置文件
def check_nginx(nginx_sbin, nginx_conf):
    output = com.getstatusoutput("%s -t -c %s" % (nginx_sbin, nginx_conf))
    return output


# 重启nginx
def reload_nginx(nginx_sbin, nginx_conf):
    pid = com.getoutput("ps aux | grep nginx| grep master|grep -v grep| awk '{print $2}'")
    if pid:
        output = com.getstatusoutput("%s -s reload" % nginx_sbin)
    else:
        output = com.getstatusoutput("%s -c %s" % (nginx_sbin, nginx_conf))
    return output


# 日志重命名
def rename_log(log, flag):
    """
    重命名log文件
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


# 分析处理日志
def check_file(loglist, today, packdate, ext):
    """
    loglist: 日志列表
    today: 今天日期
    packdate: 打包时间（packdate天前）
    ext: 文件扩展名
    """
    info = []
    for logs in loglist:
        logfiles = get_files(logs)
        for logf in logfiles:
            if os.path.isfile(logf):
                logpath = os.path.split(logf)[0]
                logname = os.path.split(logf)[1]
                # 切换工作目录
                os.chdir(logpath)
                # 切割当天日志
                newfile = str(logname.split('.')[0]) + '.%s' % today
                if logname == newfile:
                    if get_mtime(logname) is today:
                        rename_log(logname, today)
                    else:
                        info.append('%s have not log:%s/%s'% (today, logpath, newfile))
                # 打包7天前文件
                oldfile = str(logname.split('.')[0]) + '-%s.%s' % (packdate, ext)
                if logname == oldfile:
                    package_log(logname)
                else:
                    info.append('%s/%s not exists !' % (logpath, oldfile))

    return info


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

    # 读取配置文件
    f = 'conf.ini'
    config = cf.ConfigParser()
    config.read(f)

    # 打包时间
    AGO = config.getint('packdate', 'ago')
    PACKDATE = (datetime.datetime.now() - datetime.timedelta(days=AGO)).strftime("%Y-%m-%d")

    NGINX = config.get('nginx', 'sbin')
    CONF = config.get('nginx', 'conf')
    EXT = config.get('loginfo', 'ext')
    # Log
    LOG = []
    for lopts in config.options('loglist'):
        LOG.append(config.get('loglist', lopts))

    # 判断nginx配置文件是否正常
    if check_nginx(NGINX, CONF)[0]:
        # Nginx配置错误提示
        MESSAGE['Nginx-Error'].append(check_nginx(NGINX, CONF)[1])
    else:
        INFO = check_file(loglist=LOG, today=TODAY, packdate=PACKDATE, ext=EXT)
        MESSAGE['Log-Warn'] .append(INFO)
        # 重启nginx
        if reload_nginx(NGINX, CONF)[0]:
            # 重启失败提示
            MESSAGE['Nginx-Error'].append(reload_nginx(NGINX, CONF)[1])

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
