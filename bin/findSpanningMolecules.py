#!/usr/bin/python3
import sys
import pybedtools
import argparse
from intervaltree import IntervalTree
from multiprocessing import Queue, Process
import subprocess
import shlex

class NoSpanningRun:
	def __init__(self):
		self.beforeRun_bp = float("inf")
		self.afterRun_bp = float("inf")


#Add the breakpoint to the Process queue
def tallyBreakpoints(bps_queue, contig, noSpanningRun):
	if noSpanningRun.beforeRun_bp == noSpanningRun.afterRun_bp:
		bps_queue.put((contig, noSpanningRun.beforeRun_bp))
	else:		
		bps_queue.put((contig, noSpanningRun.beforeRun_bp))
		bps_queue.put((contig, noSpanningRun.afterRun_bp))

#Given the molecule intervals on a contig, check all windows of specified lengths for flanking chromium molecules. Cuts
# will be made in windows of the genome where there are no spanning molecules
def checkSpanningMolecules(intervals, window, contigLengths, contig, num_spanning, bps_queue):
	contigLength = contigLengths[contig]
	
	start_window = 0
	end_window = window

	pastStart = False
	noSpanningRun = None

	while end_window < contigLength:
		numSpanningMolecs = 0
		smallestEndPos_spanningMolecs = float("inf")
		overlap_intervals = sorted(intervals[start_window], key=lambda x:x[1], reverse=True) 
		for interval in overlap_intervals: 
			if interval.end > end_window: #last overlapping base for interval is interval.end - 1 (range is inclusive of lower limit, non-inclusive of upper limit)
				numSpanningMolecs += 1
				smallestEndPos_spanningMolecs = min(smallestEndPos_spanningMolecs, interval.end-1)
			else:
				break #sorted by decreasing end position, so if this interval isn't spanning, can break out of loop
			if numSpanningMolecs >= num_spanning:
				break #Over the threshold seen, keep going

		if numSpanningMolecs < num_spanning:
			if pastStart:
				if noSpanningRun is None: #First non-spanning interval for a new run
					noSpanningRun = NoSpanningRun()
					noSpanningRun.beforeRun_bp = end_window 
			start_window += 1
			end_window += 1
		else:
			if pastStart and noSpanningRun is not None: #We have come to the end of a valid string of non-spanning molecule windows
				noSpanningRun.afterRun_bp = start_window 
				tallyBreakpoints(bps_queue, contig, noSpanningRun)
				noSpanningRun = None
			pastStart = True
			
			end_window = max(smallestEndPos_spanningMolecs + 1, end_window + 1)
			start_window = end_window - window


#Given an input sorted BED file, find all breakpoints (regions where there are no spanning molecules), based on the specified window size
def findBreakpoints(bed_name, window_length, contigLengths, num_spanning, bps_queue):
	bedfile = pybedtools.BedTool(bed_name)
	contig = ""
	interval_tree = IntervalTree()

	for bed in bedfile:
		if bed.chrom not in contigLengths:
			continue
		if bed.chrom != contig:
			if contig != "":
				checkSpanningMolecules(interval_tree, window_length, contigLengths, contig, num_spanning, bps_queue)
				interval_tree.clear()
			contig = bed.chrom
			interval_tree[bed.start:bed.stop] = bed.name
		else: #Same chromosome, keep reading in the BED file
			interval_tree[bed.start:bed.stop] = bed.name
	#Ensuring final contig in the bed file is also checked for spanning molecules
	if contig != "":
		checkSpanningMolecules(interval_tree, window_length, contigLengths, contig, num_spanning, bps_queue)
	
	
#Launch processes to find breakpoints for partitioned contigs in parallel. Returns dictionary of identified breakpoints.
def launchFindBreakpoints(bedfile, window, num_processes, partitioned_contigLengths, num_spanning):
	processes = []
	bp_queue = Queue() 
	breakpoints = {}
	
	for i in range(0, num_processes):
		p = Process(target=findBreakpoints, args=(bedfile, window, partitioned_contigLengths[i], num_spanning, bp_queue))
		processes.append(p)
		p.start()

	while True:
		running = any(p.is_alive() for p in processes)
		while not bp_queue.empty():
			bp = bp_queue.get()
			chrom = bp[0]
			pos = int(bp[1])
			if chrom not in breakpoints:
				breakpoints[chrom] = []
			breakpoints[chrom].append(pos)
		if not running:
			break			

	for p in processes:
		p.join()
	
	return breakpoints	
	
#Reads through the fai index of the fasta file, partitioning the contigs, and tracking the contig lengths in dictionaries. Returns a 
# list of dictionaries, with one dictionary for each breakpoint-finding process to be launched. 
def findContigLengths(fasta, num_processes):
	fasta_faidx_name = fasta + ".fai"
	try:
		fasta_faidx = open(fasta_faidx_name, 'r')
		
		contig_lengths = []
		for i in range(0, num_processes):
			contig_lengths.append({})	
		
		count = 0
		for seq in fasta_faidx:
			seq = seq.strip().split("\t")
			ctg_name = seq[0]
			ctg_length = int(seq[1])
			partition = count % num_processes
			contig_lengths[partition][ctg_name] = ctg_length
			count += 1
		fasta_faidx.close()
		return contig_lengths
	
	except:
		print("Error when trying to open %s.\nGenerate the fai index file for %s with: samtools faidx %s" % (fasta_faidx_name, fasta, fasta))
		sys.exit(1)

# Given a list of breakpoints and a reference FAI file, print a BED file representing the regions of the FASTA to output.
def printBreakpoints(breakpoints, partitioned_contigLengths, outprefix, len_trim):
	breakpoints_bedString = ""

	for part in partitioned_contigLengths:
		for contig in part:
			contigLength = part[contig]
			if contig in breakpoints:
				contig_breakpoints = sorted(breakpoints[contig])
				start = 0
				contigNum = 1
				curName = "%s-%d" % (contig, contigNum)
				for bp in contig_breakpoints:
					breakpoints_bedString += "%s\t%d\t%d\t%s\n" % (contig, start, bp-len_trim, curName)
					start = bp + len_trim
					contigNum += 1
					curName = "%s-%d" % (contig, contigNum)
				if start < contigLength: #Make sure to get the final bed region
					breakpoints_bedString += "%s\t%d\t%d\t%s\n" % (contig, start, contigLength, curName)
			else: #No breakpoints, have BED for entire length of the contig.
				breakpoints_bedString += "%s\t%d\t%d\t%s\n" % (contig, 0, contigLength, contig)

	breakpoints_bed = pybedtools.BedTool(breakpoints_bedString, from_string=True).sort()
	bed_out = open(outprefix + ".breaktigs.bed", 'w')
	breakpoints_bed.saveas(outprefix + ".breaktigs.bed")
	bed_out.close()

#Use bedtools to cut the assembly based on the breakpoints identified in the breaktigs bed file, stripping Ns from beginning and end of the sequences
def cutAssembly(fasta, outprefix):
	bedfile = outprefix + ".breaktigs.bed"	
	cmd = "bedtools getfasta -fi %s -bed %s -name" % (fasta, bedfile)
	cmd_shlex = shlex.split(cmd)
	out_fasta = open(outprefix + ".breaktigs.fa", 'w')	

	cutFasta = subprocess.Popen(cmd_shlex, stdout=subprocess.PIPE, universal_newlines=True)
	for line in iter(cutFasta.stdout.readline, ''):
		line = line.strip()
		if line[0] == ">": #Header line
			out_fasta.write(line + "\n")
		else: #Sequence line, check for Ns at beginning or trailing	
			strippedNs = line.strip("Nn")
			if strippedNs == "": #Just give single N if the sequence will become empty
				strippedNs = "N"
			out_fasta.write(strippedNs + "\n")
	out_fasta.close()

def main():
	parser = argparse.ArgumentParser(description="Find misassembled regions in assembly using Chromium molecule extents")
	parser.add_argument("bed", type=str, help="Sorted bed file of molecule extents")
	parser.add_argument("-f", type=str, help="Reference genome fasta file (must have FAI index generated)", required=True)
	parser.add_argument("-d", type=int, help="Window size used to check for spanning molecules (bp) [1000]", default=1000)
	parser.add_argument("-p", type=int, help="Number of parallel processes to launch for breakpoint-finding [8]", default=8)
	parser.add_argument("-t", type=int, help="Number of base pairs to trim at contig cuts [0bp]", default=0)
	parser.add_argument("-n", type=int, help="Spanning molecules threshold (no misassembly in window if num. spanning molecules >= n [2]", default=2)
	parser.add_argument("-o", type=str, help="Prefix for output files", required=True)

	args = parser.parse_args()
	
	print ("Reading contig lengths...")	
	partitioned_contigLengths = findContigLengths(args.f, args.p)

	print("Finding breakpoints...")
	breakpoints = launchFindBreakpoints(args.bed, args.d, args.p, partitioned_contigLengths, args.n)	
	printBreakpoints(breakpoints, partitioned_contigLengths, args.o, args.t)	

	print("Cutting assembly at breakpoints...")
	cutAssembly(args.f, args.o)
	
	
if __name__ == "__main__":
	main()
