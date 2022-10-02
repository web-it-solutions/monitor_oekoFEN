# imports
from configparser import ConfigParser
from datetime import datetime
from influxdb import InfluxDBClient

import json
import os
import urllib.request

# configuration
path = os.path.dirname(__file__)

if '' != path:
    path += '/'

config = ConfigParser()
config.read([path + '_config.ini', path + '_user.ini'])

# debug mode
debug = config.getboolean('source', 'debug', fallback = False)

# connect to influxDB to persist data
def connectToInfluxDB():
    # influxDB configuration settings with fallback(s)
    influxDatabase = config.get('influxDB', 'database', fallback = 'oekofen')
    influxHost = config.get('influxDB', 'host', fallback = '127.0.0.1')
    influxPassword = config.get('influxDB', 'password', fallback = '')
    influxUser = config.get('influxDB', 'user', fallback = '')

    # influxDB port configuratioin has to be an integer
    try:
        influxPort = config.getint('influxDB', 'port', fallback = 8086)
    except ValueError as error:
        print('Error: ' + str(error))
        quit()

    # check validity of influxDB connection concerning host and port only
    try:
        influxDBClient = InfluxDBClient(influxHost, influxPort, influxUser, influxPassword, influxDatabase)
        influxDBClient.ping()
    except Exception as error:
        print('Error connecting to influxDB:')
        print('-> ' + str(error))
        quit()

    return influxDBClient

# converts data for special keys so they have 'correct' values
def convertFieldValues(data):
    for key in data:
        for field in data[key]:
            if isinstance(data[key][field], dict):
                if 'factor' in data[key][field] and 0.1 == data[key][field]['factor']:
                    data[key][field] = float(data[key][field]['val'])/10
                elif 'factor' in data[key][field] and 0.01 == data[key][field]['factor']:
                    data[key][field] = float(data[key][field]['val'])/100
                else:
                    data[key][field] = data[key][field]['val']

    return data

# collect defined data from AC ELWA-E
def getData():
    ip = config.get('source', 'ip')
    password = config.get('source', 'password')
    port = config.getint('source', 'port', fallback = 4321)

    # check for necessary config keys
    if '' == ip:
        print('Required config "ip" within [source] in _user.ini is missing!')
        quit()

    if '' == password:
        print('Required config "password" within [source] in _user.ini is missing!')
        quit()

    fields = config.get('source', 'fields')
    parts = config.get('source', 'parts')

    if '' != fields and '' == parts:
        print('If custom fields are defined, custom parts have to be defined as well!')
        quit()

    url = 'http://' + ip + ':' + str(port) + '/' + password + '/all?'
    oekofenData = json.loads(urllib.request.urlopen(url).read().decode('cp1252'))
    oekofenDataParts = dict()

    # collect all fields of all parts
    if '' == fields and '' == parts:
        for key in oekofenData:
            oekofenDataParts[key] = oekofenData[key]

        return oekofenDataParts

    # collect all fields of parts defined in _config.ini/_user.ini
    if '' == fields and '' != parts:
        for key in oekofenData:
            if key in parts:
                oekofenDataParts[key] = oekofenData[key]

        return oekofenDataParts

    # collect fields and parts defined in _config.ini/_user.ini
    for key in oekofenData:
        if key in parts:
            oekofenFields = dict()

            for field in oekofenData[key]:
                if (key + '|' + field) in fields:
                    oekofenFields[field] = oekofenData[key][field]

            oekofenDataParts[key] = oekofenFields

    return oekofenDataParts

# write collected data to defined influxDB
def writeDataToInfluxDB(parts):
    measurement = config.get('influxDB', 'measurement', fallback = 'pellematic')

    for part in parts:
        if 0 == len(parts[part]):
            return

        points = [{
            'fields': parts[part],
            'measurement': measurement,
            'tags': {
                'part': part
            }
        }]

        try:
            influxDBClient.write_points(points, time_precision = 's')
        except Exception as error:
            print('Error connecting to influxDB:')
            print('-> ' + str(error))
            quit()

# collect and persist data
influxDBClient = connectToInfluxDB()
data = getData()
data = convertFieldValues(data)
writeDataToInfluxDB(data)

if True == debug:
    print('Debug: Pellematic Condens data:')

    for part in data:
        print('Part: ' + part)

        for key in sorted(data[part]):
            print('-> ' + key + ': ' + str(data[part][key]))
