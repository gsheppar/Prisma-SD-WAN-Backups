#!/usr/bin/env python3
import cloudgenix
import argparse
from cloudgenix import jd, jd_detailed, jdout
import yaml
import cloudgenix_settings
import sys
import logging
import logging.handlers as handlers
import collections
import os
import datetime
import time
import json
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import schedule
from cloudgenix_config.pull import go_pull
import errno

# Global Vars
SDK_VERSION = cloudgenix.version
SCRIPT_NAME = 'CloudGenix: Script: Backups'
SCRIPT_VERSION = "v1"

# Set NON-SYSLOG logging to use function name

logger = logging.getLogger('event_log')
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logHandler = handlers.RotatingFileHandler('download_log.txt', maxBytes=5000000, backupCount=2)
logHandler.setLevel(logging.INFO)
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)


####################################################################
# Read cloudgenix_settings file for auth token or username/password
####################################################################

sys.path.append(os.getcwd())
try:
    from cloudgenix_settings import CLOUDGENIX_AUTH_TOKEN

except ImportError:
    CLOUDGENIX_AUTH_TOKEN = None

try:
    from cloudgenix_settings import EMAIL_USERNAME
    from cloudgenix_settings import EMAIL_PASSWORD
    from cloudgenix_settings import EMAIL_DESTINATION
    from cloudgenix_settings import DIRECTORY

except ImportError:
    EMAIL_USERNAME = None
    EMAIL_PASSWORD = None
    EMAIL_DESTINATION = None
    DIRECTORY = None

####################################################################
# Main Function
####################################################################

def backups(cgx):
    curtime_str = datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
    message = "Starting backups " + str(curtime_str)
    print("\n##############################################\n")
    print(message)
    logger.info(message)
    
    num = 0
    failed = 0
    failed_sites = []    
    for site in cgx.get.sites().cgx_content["items"]:
        num += 1
        if site["admin_state"] == "active":
            try:
                site_name = site["name"]
                token = CLOUDGENIX_AUTH_TOKEN
                directory = DIRECTORY
                go_pull(site_name, token, directory)
            except Exception as e:
                message = "Failed to backup " + site["name"]
                print(message)
                logger.info(message)
                logger.info(str(e))
                failed += 1
                failed_sites.append(site_name)
    
    if failed != 0:
        message = "Failed backing up " + str(failed) + " sites out of " + str(num) + ".\n" + str(failed_sites)
        print(message)
        logger.info(message)
        
        mail_to = EMAIL_DESTINATION
        mail_subject = "SD-WAN Backup Failure Notification"
        mail_body = message
        send_email(mail_body, mail_subject, mail_to)
        
    else:
        message = "Successfully backed up " + str(num) + " sites"
        print(message)
        logger.info(message)
        
        mail_to = EMAIL_DESTINATION
        mail_subject = "SD-WAN Backup Success Notification"
        mail_body = message
        send_email(mail_body, mail_subject, mail_to)
    
    curtime_str = datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
    message = "Finished backups " + str(curtime_str)
    logger.info(message)
    print(message)
    
    return

def send_email(mail_body, mail_subject, mail_to):
    try:
        username = EMAIL_USERNAME
        password = EMAIL_PASSWORD
        mail_from = EMAIL_USERNAME

        mimemsg = MIMEMultipart()
        mimemsg['From']=mail_from
        mimemsg['To']=mail_to
        mimemsg['Subject']=mail_subject
        mimemsg.attach(MIMEText(mail_body, 'plain'))
        connection = smtplib.SMTP(host='smtp.office365.com', port=587)
        connection.starttls()
        connection.login(username,password)
        connection.send_message(mimemsg)
        connection.quit()
        message = "Email sent to " + mail_to
        logger.info(message)
    except:
        message = "Failed to send email to " + mail_subject + " to " + mail_to
        print(message)
        logger.info(message)  
    return
                            
def go():
    ############################################################################
    # Begin Script, parse arguments.
    ############################################################################

    cgx_session = cloudgenix.API(update_check=False)

    print("{0} {1} ({2})\n".format(SCRIPT_NAME, SCRIPT_VERSION, cgx_session.controller))

    ############################################################################
    # End Login handling, begin script..
    ############################################################################

    # get time now.
    curtime_str = datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S')    
    message = "Starting Backup Script"
    print(message)
    logger.info(message)
    
    # check for Email Username
    if not EMAIL_USERNAME:
        message = "EMAIL Username missing, please check."
        print(message)
        logger.info(message)
        sys.exit()
    if CLOUDGENIX_AUTH_TOKEN:
        cgx_session.interactive.use_token(CLOUDGENIX_AUTH_TOKEN)
        if cgx_session.tenant_id is None:
            message = "AUTH_TOKEN login failure, please check token."
            print(message)
            logger.info(message)
            sys.exit()
    else:
        message = "No AUTH_TOKEN found"
        print(message)
        logger.info(message)
        sys.exit()
    
    if not DIRECTORY:
        print("Directory is missing")
        sys.exit()
    current_directory = os.getcwd()
    final_directory = os.path.join(current_directory, DIRECTORY)
    if not os.path.exists(final_directory):
        try:
            os.makedirs(final_directory)
        except OSError as exc:
            if exc.errno != errno.EEXIST:
                logger.info(str(exc))
                print(str(exc))
                sys.exit()

    cgx = cgx_session
    schedule.every().saturday.at("22:00").do(backups, cgx)

    while True:
        schedule.run_pending()
        time.sleep(30)

if __name__ == "__main__":
    go()