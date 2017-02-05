# telldus-influxdb
A simple Python script that fetches all available [Telldus](http://telldus.com) sensors from [TelldusLive] (http://live.telldus.com) and writes the readings into an [InfluxDB](https://www.influxdata.com/) TSDB

## Instructions
Add your Telldus Live API key and token at the beginning of the script. Also change to the correct values for connecting to your InfluxDB.

Start the script with:
```sh
./telldus-influxdb.py start
```
