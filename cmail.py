import smtplib
from email.message import EmailMessage
def sendmail(to,subject,body):
    server=smtplib.SMTP_SSL('smtp.gmail.com',465)#connecting to email server
    server.login('vignan.cse510@gmail.com','ynogewmbegpbzfvn')
    msg=EmailMessage()
    msg['From']='vignan.cse510@gmail.com'
    msg['Subject']=subject
    msg['To']=to
    msg.set_content(body)
    server.send_message(msg)
    server.quit()

