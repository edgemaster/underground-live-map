#!/usr/bin/python

from __future__ import division 
import urllib
import re
import simplejson as json
import time
import os
import os.path
import mx.DateTime

dir = '/srv/traintimes.org.uk/public/htdocs/map/tube/bin/'

format = 'traintimes'

api = 'http://apibeta.london.gov.uk/TrackernetWebServicev3/timetableService.aspx?Feed=4&Line=%s&StationCode=&Time='

station_locations = json.load(open(dir + 'stations.json'))
for name, str in station_locations.items():
    lng, lat = str.split(',')
    station_locations[name] = (float(lat), float(lng))


lines = {
    'B': 'Bakerloo',
    'C': 'Central',
    'D': 'District',
    'H': 'Hammersmith & Circle',
    'J': 'Jubilee',
    'M': 'Metropolitan',
    'N': 'Northern',
    'P': 'Piccadilly',
    'V': 'Victoria',
    'W': 'Waterloo & City',
}

def parse_time(s):
    """Converts time in MM:SS, or - for 0, to time in seconds"""
    if s == '-': return 0
    m = re.match('(\d+):(\d+)$', s)
    return int(m.group(1))*60 + int(m.group(2))

# Loop through the trains
out = {}
outNext = {}
for key, line in lines.items():
    sub_id = 0
    sub_ids = {}
    try:
        if time.time() - os.path.getmtime('cache/%s' % key) > 100:
            raise Exception, 'Too old'
        live = open(dir + 'cache/%s' % key).read()
    except:
        live = urllib.urlopen(api % key).read()
        fp = open(dir + 'cache/%s' % key, 'w')
        fp.write(live)
        fp.close()
    stations = re.findall('<S Code="([^"]*)" N="([^"]*)">(.*?)</S>(?s)', live)
    for station_code, station_name, station  in stations:
        platforms = re.findall('<P N="([^"]*)" Code="([^"]*)">(.*?)</P>(?s)', station)
        for platform_name, platform_code, platform in platforms:
            trains = re.findall('<T S="(.*?)" T="(.*?)" D="(.*?)" C="(.*?)" L="(.*?)" DE="(.*?)" />', platform)
            for set_id, trip_id, dest_code, time_to_station, current_location, destination in trains:
                if current_location == '': continue
                if 'Terminal 5' in station_name: continue # List doesn't have its location
                if 'Road 21' in station_name: continue # List doesn't have its location
                time_to_station = parse_time(time_to_station)
                if set_id == '000':
                    lookup = re.sub('\s*Platform \d+$', '', current_location)
                    if current_location == 'At Platform':
                        lookup = 'At %s' % station_name
                    if not sub_ids.get(lookup):
                        sub_ids[lookup] = sub_id
                        sub_id += 1
                    set_id += '-%s' % sub_ids[lookup]
                entry = {
                    'station_name': re.sub('\.$', '', station_name),
                    'platform_name': platform_name,
                    'current_location': current_location,
                    'time_to_station': time_to_station,
                    'dest_code': dest_code,
                }
                if time_to_station < out.get(key, {}).get(set_id, {}).get('time_to_station', 999999):
                    out.setdefault(key, {})[set_id] = entry
                outNext.setdefault(key, {}).setdefault(set_id, []).append(entry)
                #print '%s %s %s | %s %s %s' % (key, station_name, platform_name, set_id, time_to_station, current_location)

# Remove trains that have the same ID and dest_code, but a higher time_to_station - probably the same train
for key, ids in out.items():
    for id, arr in ids.items():
        for key2, ids2 in out.items():
            if key == key2: continue
            for id2, arr2 in ids2.items():
                if id == id2 and arr['dest_code'] == arr2['dest_code']:
                    if arr['time_to_station'] < arr2['time_to_station']:
                        if out[key].get(id2): del out[key2][id2]
                    else:
                        if out[key].get(id): del out[key][id]
        
def canon_station_name(s, line):
    """Given a station name, try and reword it to match the station list"""
    s = s.strip()
    s = re.sub('^Heathrow$', 'Heathrow Terminals 1, 2, 3', s)
    s = re.sub('^Olympia$', 'Kensington (Olympia)', s)
    s = re.sub('^Warwick Ave$', 'Warwick Avenue', s)
    s = re.sub('^Camden$', 'Camden Town', s)
    s = re.sub('^Central$', 'Finchley Central', s) # They say "Between Central and East Finchley"
    s = re.sub('\s*Platform \d+$', '', s)
    s = s + ' Station'
    s = s.replace('(Bakerloo)', 'Bakerloo').replace('Earls', 'Earl\'s') \
        .replace(' fast ', ' ') \
        .replace('\xe2\x80\x99', "'") \
        .replace('St ', 'St. ') \
        .replace('Warren St.', 'Warren Street') \
        .replace('Elephant and Castle', 'Elephant &amp; Castle') \
        .replace('Elephant Station', 'Elephant &amp; Castle Station') \
        .replace('Lambeth Station', 'Lambeth North Station') \
        .replace('Chalfont Station', 'Chalfont &amp; Latimer Station') \
        .replace('Chalfont and Latimer Station', 'Chalfont &amp; Latimer Station') \
        .replace('West Brompon', 'West Brompton') \
        .replace('Picadilly Circus', 'Piccadilly Circus') \
        .replace("Queen's' Park", "Queen's Park") \
        .replace('High Barent', 'High Barnet') \
        .replace('Bartnet', 'Barnet') \
        .replace('Faringdon', 'Farringdon') \
        .replace('Turnham Greens', 'Turnham Green') \
        .replace('Ruilsip', 'Ruislip') \
        .replace('Dagemham', 'Dagenham') \
        .replace('Edgware Road (H &amp; C)', 'Edgware Road Circle') \
        .replace('Hammersmith (Circle and H&amp;C)', 'Hammersmith') \
        .replace('Shepherds Bush (Central Line)', "Shepherd's Bush") \
        .replace('Terminals 123', 'Terminals 1, 2, 3').replace('Terminal 1,2,3', 'Terminals 1, 2, 3') \
        .replace('Woodford Junction', 'Woodford') \
        .replace("King's Cross Station", "King's Cross St. Pancras Station") \
        .replace("Kings Cross Station", "King's Cross St. Pancras Station") \
        .replace('Central Finchley', 'Finchley Central').replace('District and Picc', 'D &amp; P') \
        .replace('South Fields', 'Southfields') \
        .replace('Regents Park', "Regent's Park") \
        .replace('Bromley-by-Bow', "Bromley-By-Bow") \
        .replace('Brent Oak', 'Burnt Oak') \
        .replace('St. Johns Wood', "St. John's Wood") \
        .replace('Totteridge and Whetstone', 'Totteridge &amp; Whetstone') \
        .replace('Newbury Park Loop', 'Newbury Park') \
        .replace('Harrow-on-the-Hill', 'Harrow on the Hill')
    if s == 'Edgware Road Station' and line == 'B':
        s = 'Edgware Road Bakerloo Station'
    if s == 'Edgware Road Station' and line != 'B':
        s = 'Edgware Road Circle Station'
    return s

for line, ids in out.items():
    for id, arr in ids.items():
        if 'Sidings' in arr['current_location']: continue
        if 'North Acton Junction' in arr['current_location']: continue
        if 'Terminal 5' in arr['current_location']: continue # List doesn't have its location
        if 'Road 21' in arr['current_location']: continue # List doesn't have its location
        if 'ALperton' in arr['current_location']: continue # List doesn't have its location
        if 'Headstone Lane' in arr['current_location']: continue # List doesn't have its location
        if 'Depot' in arr['current_location']: continue
        station_name = canon_station_name(arr['station_name'], line)
        if arr['current_location'] == 'At Platform':
            arr['location'] = station_locations[station_name]
        m = re.match('(?:South of|Leaving|Left) (.*?)(?: towards .*)?$', arr['current_location'])
        if m:
            location_1 = station_locations[canon_station_name(m.group(1), line)]
            location_2 = station_locations[station_name]
            fraction = 30 / (time_to_station + 30)
            arr['location'] = (location_1[0] + (fraction*(location_2[0]-location_1[0])), location_1[1] + (fraction*(location_2[1]-location_1[1])))
        m = re.match('Between (.*?) and (.*)', arr['current_location'])
        if m:
            location_1 = station_locations[canon_station_name(m.group(1), line)]
            location_2 = station_locations[canon_station_name(m.group(2), line)]
            max = time_to_station+30 if time_to_station > 150 else 180
            fraction = (max-time_to_station) / max
            arr['location'] = (location_1[0] + (fraction*(location_2[0]-location_1[0])), location_1[1] + (fraction*(location_2[1]-location_1[1])))
        m = re.match('Approaching (.*)', arr['current_location'])
        if m:
            # Don't know where we were previously, can't be bothered to work it out, needs to store history!
            arr['location'] = station_locations[canon_station_name(m.group(1), line)]
   
if format=='traintimes':
    outJ = {
        'station': 'London Underground',
        'center': 'new GLatLng(51.507, -0.143)',
        'lastupdate': mx.DateTime.ARPA.str(mx.DateTime.now()),
        'span': 'new GLatLng(0.3, 0.9)',
        'trains': [],
        'stations': [],
    }
    for line, ids in out.items():
        for id, arr in ids.items():
            if 'location' not in arr: continue
            next = []
            outNext[line][id].sort(lambda x,y: cmp(x['time_to_station'], y['time_to_station']))
            for n in outNext[line][id]:
                stat = canon_station_name(n['station_name'], line)
                location = station_locations[stat]
                mins = n['time_to_station']/60
                if int(mins)==mins:
                    mins_p = '%d' % mins
                else:
                    mins_p = '%.1f' % mins
                next.append({
                    'point': 'new GLatLng(%s,%s)' % location,
                    'name': stat,
                    'mins': mins,
                    'dexp': 'in %s minute%s' % (mins_p, '' if n['time_to_station']==60 else 's'),
                })
            outJ['trains'].append({
                'point': 'new GLatLng(%s,%s)' % arr['location'],
                'next': next,
                'left': '',
                'id': '%s-%s' % (line, id),
                'title': lines[line] + ' train (' + id + ')',
            })
    grr = json.dumps(outJ, indent=4)
    grr = re.sub('"(new GLatLng\([^)]*\))"', r'\1', grr)

    stations = open(dir + 'london-stations-new2.js').read()
    grr = grr[:-2] + ',\n' + stations + '}' 

    fp = open(dir + '../data/london.jsN', 'w')
    fp.write(grr)
    fp.close()
    os.rename(dir + '../data/london.jsN', dir + '../data/london.js')

