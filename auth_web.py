#! /usr/bin/env python
import json
import os
import urllib
import cherrypy
import requests
import boto3
import uuid
from alexa_client.settings import DEVICE_TYPE_ID, CLIENT_ID, CLIENT_SECRET
from cherrypy.lib.httputil import parse_query_string

sessions = {}

class Start(object):
    def index(self, **params):
        # Get the ID for this user from the query string
        query_string = parse_query_string(cherrypy.request.query_string)
        user_id = query_string["user_id"]

        # Create a session ID for this interaction
        session_id = str(uuid.uuid4())
        sessions[session_id] = user_id
        print("UserID: " + user_id + " Session: " + sessions[session_id])

        scope = "alexa_all"
        sd = json.dumps({
            "alexa:all": {
                "productID": DEVICE_TYPE_ID,
                "productInstanceAttributes": {
                    "deviceSerialNumber": user_id
                }
            }
        })
        url = "https://www.amazon.com/ap/oa"
        callback = cherrypy.url() + "authresponse"
        payload = {
            "client_id": CLIENT_ID,
            "scope": "alexa:all",
            "scope_data": sd,
            "response_type": "code",
            "redirect_uri": callback
        }
        req = requests.Request('GET', url, params=payload)
        p = req.prepare()

        cherrypy.response.cookie['session_id'] = session_id
        cherrypy.response.cookie['session_id']['path'] = '/'
        raise cherrypy.HTTPRedirect(p.url)

    def authresponse(self, var=None, **params):
        session_id = cherrypy.request.cookie['session_id'].value
        print("Cookie SessionID: " + str(session_id))
        print("Sessions: " + str(sessions))
        user_id = sessions[str(session_id)]

        print("AuthResponse SessionID: " + session_id + " UserID: " + user_id)

        code = urllib.quote(cherrypy.request.params['code'])
        callback = cherrypy.url()
        payload = {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": callback
        }
        url = "https://api.amazon.com/auth/o2/token"
        r = requests.post(url, data=payload)
        resp = r.json()
        print(str(resp))
        refresh_token = resp['refresh_token']
        self.save_to_dynamo(user_id, refresh_token)
        return "Success! You can now chat with Alexa!"

    def save_to_dynamo(self, user_id, avs_token):
        # Get the service resource.
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table('alexa_chat_user')
        table.put_item(
            Item={
                'user_id': user_id,
                'avs_token': avs_token
            }
        )

    index.exposed = True
    authresponse.exposed = True

use_ssl = os.environ["USE_SSL"] == "False"
if (use_ssl):
    server_config={
        'server.socket_host': '0.0.0.0',
        'server.socket_port': 3000,

        'server.ssl_module':'pyopenssl',
        'server.ssl_certificate':'./ssl.crt',
        'server.ssl_private_key':'./ssl.pem',
        'server.ssl_certificate_chain':'./ssl-chain.crt'
    }
else:
    server_config={
        'server.socket_host': '0.0.0.0',
        'server.socket_port': 3000
    }

cherrypy.config.update(server_config);
print('Open http://localhost:3000 to login in amazon alexa service')
cherrypy.quickstart(Start())
