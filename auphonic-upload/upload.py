#!/usr/bin/python
# -*- coding: UTF-8 -*-

import os
import sys
import argparse
from time import time, sleep
import re
import requests
from poster.encode import multipart_encode
import xml.etree.ElementTree as ET

parser = argparse.ArgumentParser(description='Watch a Folder for Video-Recordings, associate them with Talks from a Pentabarf-XML and upload the videos with metadata from the xml to Auphonic for further processing')
parser.add_argument('--schedule',
	required=True,
	help='url to a pentabarf schedule.xml')

parser.add_argument('--recordings',
	required=True,
	help='path of a folder with recording-files (mostly videos)')

parser.add_argument('--finished',
	help='path of a folder where uploaded files are moved to (defaults to a subfolder "finished" inside the recordings-folder)')

parser.add_argument('--auphonic-login',
	dest='auphonic',
	default=os.path.expandvars('$HOME/.auphonic-login'),
	help='path of a file containing "username:password" of your auphonic account')

parser.add_argument('--auphonic-preset',
	dest='preset',
	help='UUID of auphonic preset which should be used after uploading')

args = parser.parse_args()
if args.finished == None:
	args.finished = os.path.join(args.recordings, 'finished')


# try to read the auphonic login-data file
with open(args.auphonic) as fp:
	auphonic_login = fp.read().strip().split(':', 1)



# Download the Events-Schedule and parse all Events out of it. Yield a tupel for each Event
def fetch_events():
	print('downloading pentabarf schedule')

	# destination list of events
	events = {}

	# download the schedule
	r = requests.get(args.schedule)

	# check HTTP-Response-Code
	if r.status_code != 200:
		print('download failed')
		return events

	# parse into ElementTree
	schedule = ET.fromstring(r.text)

	# iterate all days
	for day in schedule.iter('day'):
		# iterate all rooms
		for room in day.iter('room'):
			# iterate events on that day in this room
			for event in room.iter('event'):
				# aggregate names of the persons holding this talk
				personnames = []
				for person in event.find('persons').iter('person'):
					personnames.append(person.text)

				# yield a tupel with the event-id, event-title and person-names
				talkid = int(event.get('id'))
				events[talkid] = {
					'id': talkid,
					'title': event.find('title').text,
					'subtitle': event.find('subtitle').text,
					'abstract': event.find('abstract').text,
					'description': event.find('description').text,
					'personnames': ', '.join(personnames)
				}

	return events



# an adapter which makes the multipart-generator issued by poster accessable to requests
# based upon code from http://stackoverflow.com/a/13911048/1659732
class IterableToFileAdapter(object):
	def __init__(self, iterable):
		self.iterator = iter(iterable)
		self.length = iterable.total

	def read(self, size=-1):
		return next(self.iterator, b'')

	def __len__(self):
		return self.length

# define a helper function simulating the interface of posters multipart_encode()-function
# but wrapping its generator with the file-like adapter
def multipart_encode_for_requests(params, boundary=None, cb=None):
	datagen, headers = multipart_encode(params, boundary, cb)
	return IterableToFileAdapter(datagen), headers

# this is your progress callback
def progress(param, current, total):
	sys.stderr.write("\ruploading {0}: {1:.2f}% ({2:d} MB of {3:d} MB)".format(param.filename if param else "", float(current)/float(total)*100, current/1024/1024, total/1024/1024))
	sys.stderr.flush()



def upload_file(filepath, event):
	print "creating Auphonic-Production for Talk-ID {0} '{1}'".format(event['id'], event['title'])

	params = {
		"title": event['title'],
		"subtitle": event['subtitle'],
		"artist": event['personnames'],
		"summary": event['description'] if event['description'] else event['abstract'],
		"action": "start",

		"input_file": open(filepath, 'rb')
	}
	if args.preset:
		params['preset'] = args.preset

	datagen, headers = multipart_encode_for_requests(params, cb=progress)

	r = requests.post(
		'https://auphonic.com/api/simple/productions.json',
		auth=(auphonic_login[0], auphonic_login[1]),
		data=datagen,
		headers=headers
	)

	print ""

	if r.status_code == 200:
		return True

	else:
		print "auphonic-upload failed with response: ", r, r.text
		return False


# initial download of the event-schedule
events = fetch_events()
eventsage = time()

pattern = re.compile("[0-9]+")

while True:
	# check age of event-schedule
	if time() - eventsage > 60*10:
		# re-download schedule when it's older then 10 minutes
		print('pentabarf schedule is >10 minutes old, re-downloading')

		# redownload
		events = fetch_events()
		eventsage = time()

	# iterate all files in the recordings-folder
	for filename in os.listdir(args.recordings):
		filepath = os.path.join(args.recordings, filename)

		# files, i said!
		if not os.path.isfile(filepath):
			continue

		# test if the filepath starts with a number and retrieve it
		match = pattern.match(filename)
		print('found file {0} in recordings-folder'.format(filename))
		if not match:
			print('"{0}" does not match any event in the schedule, skipping'.format(filename))
		else:
			talkid = int(match.group(0))
			if talkid in events:
				event = events[talkid]
				if upload_file(filepath, event):
					print('done, moving to finished-folder')
					os.rename(filepath, os.path.join(args.finished, filename))
				else:
					print('upload FAILED! trying again, after the next Maus')


	# sleep half a minute
	print('nothing to do, sleeping half a minute')
	sleep(30)

print('all done, good night.')

