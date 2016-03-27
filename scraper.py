###############################
## Karl Holub - holub008@umn.edu
## a script to download all the world cup cross country results from the FIS page
## start at the all results page, then drill down into XC WC races.
## store results in the following directory structure:
## results -> [M|F] -> [YEAR] -> [EVENT].tsv
## contents of the tsv are a sequence of FIS CODE\tname\tplacement\ttime\n 
###############################

import requests
import re
import threading
import sys
import math
import datetime
import os

from HTMLParser import HTMLParser

dir_make_mutex = threading.Lock()

NTHREADS = 20 ## number of threads to 

QUERY_FORMAT = "http://data.fis-ski.com/global-links/all-fis-results.html?seasoncode_search=all&sector_search=%s&gender_search=all&category_search=%s&date_from=begin&search=Search&limit=%d&rec_start=%d"

RES_LIM = 100 ## this is the api imposed maximum- any larger value defaults to 100

## parameters to filter the results on- 
GENDERS = ["M","F"]
SECTOR = "CC" ## we want cross country results 
CATS = ["WC","SWC","OWG","WSC"] ## we want olympic, world cup, or world cup stage results


def get_event_urls(cat):
	"""
		get the url of the top level events that will drill down into individual events
		returns a list of urls
	"""
	rec_start =0
	has_records = True
	race_urls = []
	
	while(has_records):
		target = QUERY_FORMAT%(SECTOR,cat,RES_LIM,rec_start)
		
		try:
			req = requests.get(target)
			##parsing the result html to get result urls
			if req.status_code == 200:
				html = req.text
				races_on_page = parse_race_urls(html)
				race_urls += races_on_page
			else:
				sys.stderr.write("Oops, you got an unexpected response looking for events at the top level\n")
				sys.exit(0)
				
			if len(races_on_page) == 0:
				has_records = False

			rec_start += len(races_on_page)
		except:
			sys.stderr.write("ignoring...failed to submit event search at url: %s\n"%(target))
			break
			
		
	return race_urls

def parse_race_urls(html):
	"""
		strip the url of the races for top level events by parsing result page html
	"""	
	##just get the <tbody>...</tbody> xml
	start = html.find("<tbody>")
	end = html.find("</tbody>")
	table = html[start+len("<tbody>"):end]
	
	##could just hack this- using an html parser for extensiblilty
	p = EventTableParser()
	p.feed(table)
	
	return p.get_urls()

class EventTableParser(HTMLParser):
	"""
		a subclass of HTMLParser to read urls for top layer events
	"""
	def __init__(self):
		HTMLParser.__init__(self)
		self.in_tr = True
		self.in_td = False
		self.in_url_div = False
		self.got_url = False
		self.urls = []
	
	def handle_starttag(self,tag,attrs):
		if tag == "td":
			self.in_td = True
		elif tag == "tr":
			self.in_tr = True
			
		elif tag == "div" and self.in_td:
			if len(attrs) > 0 and len(attrs[0]) == 2 and attrs[0][1] == "wrapimg":
				self.in_url_div = True
			#else ignore
			
		elif tag == "a" and self.in_url_div:
			##avoid duplicates
			if not self.got_url:  
				
				## parse the anchor attributes to find the href
				for attr in attrs:
					if len(attr) == 2:
						if attr[0] == "href":
							self.urls.append(attr[1])
							self.got_url = True
						
	def handle_endtag(self,tag):
		if tag == "td":
			self.in_td = False
		elif tag == "tr":
			self.in_tr = False
			self.got_url = False
		elif tag == "div":
			self.in_url_div = False
			
	def get_urls(self):
		return self.urls
				
def get_race_results(events):
	"""
		called in parallel
		given a list of urls corresponding to events, generate individual race output files
	"""
	
	race_list = []
	
	for event in events:
		p = RaceTableParser(event)
		try:
			req = requests.get(event)
			if req.status_code == 200:
				html = req.text
				p.feed(html)
				
				race_list += p.get_races()
			else:
				sys.stderr.write("Received an unexpected response code in getting race data\n")
				sys.exit(0)
		except:
			sys.stderr.write("ignoring... failed to submit race result request to url: %s"%(event))
	
	print "received %d events, parsed out %d races"%(len(events),len(race_list))
	
	for race in race_list:
		if not "qual" in race.name and not "Qual" in race.name and not "Rel" in race.name and not "rel" in race.name:
			race.write_result_to_file() 
	
class RaceTableParser(HTMLParser):
	"""
		a subclass of HTMLParser to read urls for races within events
		todo rewrite this turned into complicated barf
	"""
	def __init__(self,e):
		HTMLParser.__init__(self)
		self.table_count = 0
		self.table_depth = 0
		self.in_tbody = False
		
		self.tr_depth = 0
		
		self.td_count = 0
		self.td_depth = 0
		
		self.a_depth = 0
		self.a_count_d1 = 0
		
		self.event_url = e
		
		self.current_race = Race()
		self.races = []
	
	def handle_starttag(self,tag,attrs):
		
		if tag == "table":
			self.table_depth += 1
						
			if self.table_depth ==1:
				self.table_count += 1
			
		elif tag == "tbody":
			self.in_tbody = True
			
		elif self.in_tbody and self.table_count ==1 and self.table_depth == 1:	
			##only consider the tr if we are looking at the race table (first one)
			if tag == "tr":
				self.tr_depth += 1
				
			elif tag == "td" and self.tr_depth == 1:
				self.td_depth += 1
				if self.td_depth == 1:
					self.td_count += 1
				
			elif tag == "a" and self.td_depth==1:
				self.a_depth += 1
							
				if self.td_count == 4 and self.a_depth == 1:
					for attr in attrs:
						if len(attr) == 2:
							if attr[0] == "href":
								self.current_race.url = attr[1]
			
	def handle_endtag(self,tag):
		if tag == "tbody":
			self.in_tbody = False
			
		elif tag == "table":
			self.table_depth -= 1
		
		elif self.table_count ==1 and self.table_depth ==1  and self.in_tbody:
			
			if tag == "tr":
				self.tr_depth -= 1
				
				if self.td_count > 1:
					if self.current_race.url == "NA":
						sys.stderr.write("failed url- no anchor href for race at event url: %s\n"%(self.event_url))
					else:
						self.races.append(self.current_race)
						self.current_race = Race()
				
				self.td_count = 0
		
			elif tag == "td" and self.tr_depth == 1:
				self.td_depth -= 1
		
			elif tag == "a" and self.td_depth ==1:
				self.a_depth -= 1
						
	def handle_data(self,data):
		if self.table_count == 1 and self.table_depth == 1 and self.a_depth == 1 and self.td_depth == 1: ##again, ignore any nested table entries
				
			if self.td_count == 2:
				##reformat dd.mm.yyyy to yyyy.mm.dd
				try:
					self.current_race.date = datetime.datetime.strptime(data, '%d.%m.%Y').strftime('%Y.%m.%d')
				except:
					sys.stderr.write("Unexpected date format:\t%s\tfound at url:\t%s\n"%(data,self.event))
					sys.exit(0)
					
			elif self.td_count == 5:
				self.current_race.codex = data
			
			elif self.td_count == 6:
				self.current_race.name = data
			
			elif self.td_count == 7:
				self.current_race.gender = data
			
			
	def get_races(self):
		return self.races

class Race:
	"""
		a structure for storing race data
	"""
	def __init__(self):
		self.url = "NA"
		self.codex = "NA"
		self.date = "NA"
		self.gender = "NA"
		self.name = "NA"
	
	def write_result_to_file(self):
		#TODO
		try:
			req = requests.get(self.url)
			
			if req.status_code == 200:
				p = ResultParser()
				p.feed(req.text)
				
				file_path = "./results/%s/%s/"%(self.gender,self.get_year())
				
				## ensuring that the directory exists, with consideration for async threads
				dir_make_mutex.acquire()
				if not os.path.exists(file_path):
					os.makedirs(file_path)
				dir_make_mutex.release()
					
				outfile = file("%s/%s_%s.tsv"%(file_path,self.date,self.codex),'w')
				
				for result in p.get_results():
					outfile.write(result.to_tab_string())
					
				outfile.close()
				
			else:
				sys.stderr.write("Error: unexpected response code for a race result request")
				sys.exit(0)
			
		except:
			sys.stderr.write("ignoring... failed to submit individual race request to url: %s\n"%(self.url))
			
	def get_year(self):
			return self.date[0:4]
		
class ResultParser(HTMLParser):
	"""
		a subclass of HTMLParser to read race results
	"""
	def __init__(self):
		HTMLParser.__init__(self)
		self.table_count = 0
		self.in_tr = False
		self.td_count = 0
		self.in_a = False
		
		self.current_result = Result()
		self.results = []
	
	
	def handle_starttag(self,tag,attrs):
		if tag == "table":
			self.table_count += 1
			
		##results will be in the 2nd table on the page
		if self.table_count == 2:
			if tag == "tr":
				self.in_tr = True
			
			elif tag == "td" and self.in_tr:
				self.td_count += 1
			
			elif tag == "a" and self.in_tr:
				self.in_a = True
			
	def handle_endtag(self,tag):
		if tag == "tr" and self.table_count == 2 and self.td_count > 1:
			
			self.in_tr = False
			self.td_count = 0
			
			self.results.append(self.current_result)
			self.current_result = Result()
		
		elif tag=="a" and self.table_count ==2 and self.in_tr:
			self.in_a =False
			
	def handle_data(self,data):
		"""
			I do not understand the super parser, is passing in data twice due to the esacped space
		"""
		
		if not data.isspace() and self.in_tr: ##will only be set in the 2nd table
		
			if self.td_count == 1:
				self.current_result.placement = data
			
			elif self.td_count == 3:
				self.current_result.fis_code = data
			
			elif self.td_count == 7:
				self.current_result.time = data
		
			elif self.in_a and self.td_count ==4:
				self.current_result.name = data
				
	def get_results(self):
		return self.results
		
class Result:
	def __init__(self):
		self.placement = "NA"
		self.fis_code = "NA"
		self.name = "NA"
		self.time = "NA"
		
	def to_tab_string(self):
		taby = "%s\t%s\t%s\t%s\n"%(self.fis_code, self.name, self.placement, self.time)
		##remove unicode
		return re.sub(r'[^\x00-\x7f]',r'', taby)
				
########################################
## start control flow
########################################

visited_urls = set()

for cat in ["WC"]:#CATS:
	event_urls = get_event_urls(cat)
	
	##getting the unique urls
	event_set = set(event_urls)
	new_urls = list(event_set - visited_urls)
	visited_urls |= event_set
	
	##grouping the urls for threads- not perfectly flat groups
	jump = int(math.ceil(len(new_urls)/float(NTHREADS))) ##ceil to ensure all urls are assigned
	
	if jump > 0:
		event_groups = [new_urls[base:base+jump] for base in xrange(0,len(new_urls),jump)]

		print "found %d events total\n\n"%(sum([len(x) for x in event_groups]))
		
		t_running = []
		##spin up threads to handle i/o bound race result scraping
		for events in event_groups:
			t = threading.Thread(target= get_race_results, args=(events,))
			t.start()
			t_running.append(t)
		
		##not the most efficient, but doable for this small script
		##gather all threads before proceeding to next iteration
		for t in t_running:
			t.join()
			
##"http://data.fis-ski.com/dynamic/event-details.html?event_id=24298&cal_suchsector=CC"