############################################
## holub008@umn.edu
## a completely non-optimized script for computing harkness scores (harkness, 1967)
#############################################

import os
import sys

DEFAULT_SCORE = 1000
OUT_PATH = "./harkness.tsv"
MIN_DATE = "2000.00.00"
MIN_RACES = 10

class SupportFiler:
	def __init__(self,g):
		self.gender = g
		
		self.date_results = {} # date, [skier1,skier2,...,skier3] pairs
		
		self.date_codex = {} # for looking up the event page- should be date,[codex1,codex2,] pairs
		
		self.name_lookup ={} #fis_id,name pairs
	
	def add_race(self, results, date, codex):
		"""
			record a race for a given date
		"""

		results.sort(key = lambda x: int(x[2]))
		
		ordered = [x[0] for x in results]
		
		if not date in self.date_results:
			self.date_results[date] = ordered
		else:
			sys.stderr.write("Warn: multiple races on one day, ignoring...\n")
		
		
		##keep track of names
		for entry in results:
			if not entry[0] in self.name_lookup:
				self.name_lookup[entry[0]] = entry[1]


		##keep track of other metadata
		if not date in self.date_codex:
			self.date_codex[date] = []
		self.date_codex[date].append(codex)
					

	def write_results(self):
		"""
			write all the date_results to file
		"""

	def write_date_codex(self):
		"""
			write a file date_lookup.tsv of all the dates encountered, in sorted order, paired with the event codex
		"""
	
	def write_name_id(self):
		"""
			write a file id_lookup.tsv with fis_id, name pairs
		"""
		
	def write_all(self):
		"""
		
		"""
	
def filter_valid_results(results):
	"""
		check if the file at <path> has the appropriate tsv structure, a fis id in the first field
		and a ranking in the third field
	"""
	
	subset = []
	
	for entry in results:
		##need 4 fields
		if len(entry) == 4:
			## need a valid fis id
			if len(entry[0]) == 7 and entry[0].isdigit():
				if len(entry[2]) > 0 and entry[2].isdigit():
					subset.append(entry)
	return subset
	

def find_all_results(gender):
	"""
		generate a list of all files across all years
	"""
	gender_path = "./results/%s/"%(gender)
	year_dirs = [gender_path + x for x in os.listdir(gender_path)]
	
	##code barf- just rewrite if problem :)
	race_tsvs = [y for x in [["%s/%s"%(year_dir,z) for z in os.listdir(year_dir)] for year_dir in year_dirs] for y in x]
	
	return race_tsvs

def run_harkness(filer):
	"""
		given a filer object, perform an elo ranking
	"""
	
	runner = HarknessRunner(filer.date_results, filer.name_lookup)
	
	for date in sorted(filer.date_results.keys()):
		print "handling %s results"%(date)
		runner.tally_race(date,filer.date_results[date])
		
	runner.write_hark_to_file()

class HarknessRunner():
	
	def __init__(self, date_results, n_lookup):
		self.name_lookup = n_lookup
	
		self.col_labels = sorted(date_results.keys())
		self.row_labels = n_lookup.keys()
		self.most_recent_date = "0000.00.00"
		
		##initialize all elo scores as -1, until a skier's first race
		self.hark_scores = [[-1 for x in xrange(0,len(self.col_labels))] for y in xrange(0,len(self.row_labels))]
		self.race_count = {}
		
	def tally_race(self, date, results):
		if date < self.most_recent_date: ##string comp on yyyy.mm.dd
			sys.stderr.write("Warning: you are delivering games out of time order.")
		
		self.most_recent_date = date
		
		##compute the skier average of this race
		score_sum = 0
		for skier_id in results:
			score_sum += self.get_hark(date,skier_id)
		
		if len(results) >0:
			avg_score = score_sum / float(len(results))
		else:
			avg_score = -1
			
		for i,skier_id in enumerate(results):
			
			pct = 100*(len(results)-i)/float(len(results)-1)
			update = 10*(pct-50.0)

			self.add_hark(date, skier_id, avg_score + update)
			
			##keep track of the number of races participated in
			if not skier_id in self.race_count:
				self.race_count[skier_id] = 0
			self.race_count[skier_id] += 1
		
		
		## now fill in elo ratings for people who didn't compete in this race
		self.update_hark(date)
		
	def add_hark(self, date, skier_id, score):
		date_ix = self.col_labels.index(date)
		skier_ix = self.row_labels.index(skier_id)
		
		self.hark_scores[skier_ix][date_ix] = score
		
	def get_hark(self, max_date, skier_id):
		"""
			given a skier_id, get the up to date elo score
			will return default=1000 if the player is yet to have an elo score recorded
		"""
		
		date_ix = self.col_labels.index(max_date)
		skier_ix = self.row_labels.index(skier_id)
		if date_ix > 0:
			return self.hark_scores[skier_ix][date_ix-1]
		else:
			return DEFAULT_SCORE
	
	def update_hark(self, date):
		"""
			fill in elo for skiers that did not race in the last date
			todo time decay- will also need to update the default_score scoring mechanism(puts later skiers at disadvantage) i.e. if has_skied(skier), then use decay
			keep a structure for time from the last event
		"""
		date_ix = self.col_labels.index(date)
		if date_ix > 0:
			for i in range(0,len(self.hark_scores)):
				if self.hark_scores[i][date_ix] < 0:
					self.hark_scores[i][date_ix] = self.hark_scores[i][date_ix-1]
		else:
			for i in range(0,len(self.hark_scores)):
				if self.hark_scores[i][date_ix] < 0:
					self.hark_scores[i][date_ix] = DEFAULT_SCORE

	def write_hark_to_file(self):
	
		##write the elo scores, with row/column headers		
		file = open(OUT_PATH,'w')
		file.write("\tName\t%s\n"%('\t'.join(self.col_labels)))
		
		for i in range(0,len(self.hark_scores)):
			skier_id = self.row_labels[i]
			
			##only want to consider frequent racers
			if self.race_count[skier_id] >= MIN_RACES:
				
				name = self.name_lookup[skier_id]
			
				file.write("%s\t%s"%(self.row_labels[i],name))
				for j in range(0,len(self.hark_scores[0])):
					file.write("\t%d"%(self.hark_scores[i][j]))
				file.write('\n')
		
		file.close()
		
		
###############################
##start control flow
###############################

gender = "M"
all_data = find_all_results(gender)

filer = SupportFiler(gender)

for file in all_data:
	
	##first getting race data
	metadata = file.split('/')
	fname_fields = metadata[4].split("_")
	date = fname_fields[0]
	codex = fname_fields[1]
	
	if date > MIN_DATE:
		##now reading in the results
		f = open(file,"r")
		contents = [x.split('\t') for x in f.readlines()]
		f.close()
		
		results = filter_valid_results(contents)
		
		filer.add_race(results,date,codex)
	
run_harkness(filer)