#!/usr/bin/env python

import json
import oauth.oauth as oauth
import requests
import sys
import time
import logging
from daemon import runner

# Telldus Auth keys - !Change these to your own!
public_key = "FEHUVEW84RAFR5SP22RAJLSKFUAFRUNU"
private_key = "ZUXEVEGA9USTAZEWKLSJHFHLKJ69U6EF"
token = "5b6a46a4a73123ec1502e0000000000c05873cc11"
token_secret = "e6167bb7216a200000000000a45afdea"

# InfluxDB connections settings
host = 'localhost'
port = 8086
user = 'root'
password = 'root'
dbname = 'telldus'

TELLDUS_URL="https://api.telldus.com"
INTERVAL = 600

PIDFILE = '/var/run/telldus-influxdb.pid'
LOGFILE = '/var/log/telldus-influxdb.log'

class TelldusError(Exception):
    pass

class InfluxDbError(Exception):
    pass

# Mostly taken from https://github.com/rlnrln/telldus-exporter
class TelldusLive:

    def get(self, method, params=None):
        consumer = oauth.OAuthConsumer(public_key, private_key)

        oauthtoken = oauth.OAuthToken(token, token_secret)

        oauth_request = oauth.OAuthRequest.from_consumer_and_token(
                consumer, token=oauthtoken, http_method='GET', http_url=TELLDUS_URL + "/json/" + method, parameters=params)
        oauth_request.sign_request(oauth.OAuthSignatureMethod_HMAC_SHA1(), consumer, oauthtoken)
        headers = oauth_request.to_header()
        headers['Content-Type'] = 'application/x-www-form-urlencoded'

        response = requests.get('%s/json/%s' % (TELLDUS_URL, method), headers=headers, params=params)

        if response.status_code != 200:
            logger.error("Failed to read from TelldusLive: " + response.text)
            raise TelldusError(response.text)

        return json.loads(response.text)

        
class InfluxDB:

    def __init__(self, host='localhost', port=8086, username='root', password='root', database=None):
        """Construct a new InfluxDB object."""
        self.__host = host
        self.__port = int(port)
        self._username = username
        self._password = password
        self._database = database

        
    def write(self, measurement, tags, fields, time=None):
        data = measurement
        
        for k,v in tags.iteritems():
            data += "," + k + "=" + v
            
        data += " "
        
        for k,v in fields.iteritems():
            if data[-1] != " ":
                data += ","
                
            data += k + "=" + v
        
        if time != None:
            data += " " + time
            
        url = "http://{0}:{1}/write?db={2}".format(self.__host, self.__port, self._database)
        response = requests.post(url, data=data)

        if response.status_code != 204:
            logger.error("Failed to write to InfluxDb: " + response.text)
            raise InfluxDbError("Failed to write to InfluxDb")

        logger.info("Measurement for %s saved" % measurement)
        
        
class TelldusInfluxDb:

    def __init__(self, telldus, influxdb):
        self._telldus = telldus
        self._influxdb = influxdb

        
    def saveSensors(self):
        for sensor in self._telldus.get('sensors/list')['sensor']:
            sensordata = self._telldus.get('sensor/info', params = { 'id': sensor['id'] })

            tags = { 'sensorId': sensor['id'], 'name': sensor['name'] }
            fields = { 'battery': sensordata['battery']}
            
            for data in sensordata['data']:
                fields.update({ data['name']: data['value'] })

            self._influxdb.write(sensor['clientName'], tags, fields)

        
# Daemon code from http://www.gavinj.net/2012/06/building-python-daemon-process.html
class Daemonize:
    def __init__(self):
        self.stdin_path = '/dev/null'
        self.stdout_path = '/dev/null'
        self.stderr_path = '/dev/null'
        self.pidfile_path =  PIDFILE
        self.pidfile_timeout = 5
        
    def run(self):
        logger.info("Daemon starting")
        telldus = TelldusLive()
        influx = InfluxDB(host, port, user, password, dbname)
        handler = TelldusInfluxDb(telldus, influx)
        
        while True:
            try:
                handler.saveSensors()
            except (TelldusError, InfluxDbError):
                logger.error("Failed to fetch/save sensors! Will try again in next interval.")

            # The daemon will repeat your tasks according to this variable
            time.sleep(INTERVAL)


if __name__ == "__main__":
    logger = logging.getLogger("telldus-influxdb")
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    handler = logging.FileHandler(LOGFILE)
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    if "run-once" in sys.argv:
        telldus = TelldusLive()
        influx = InfluxDB(host, port, user, password, dbname)
        handler = TelldusInfluxDb(telldus, influx)
        handler.saveSensors()
    else:
        daemon = Daemonize()
        daemon_runner = runner.DaemonRunner(daemon)
    
        # This ensures that the logger file handle does not get closed during daemonization
        daemon_runner.daemon_context.files_preserve=[handler.stream]

        try:
            daemon_runner.do_action()
            logger.info("Daemon stopping")
        except Exception as ex:
            logger.info("Daemon stopping! " + ex)
