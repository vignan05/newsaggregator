from itsdangerous import URLSafeTimedSerializer
from key import secret_key
#import os
def token(email,salt):
    serializer=URLSafeTimedSerializer(secret_key)
    return serializer.dumps(email,salt=salt)
'''token=serializer.dumps('vignanvijju555@gmail.com',salt='confirmation')
print(token)
print(serializer.loads(token,salt='confirmation',max_age=150))'''
