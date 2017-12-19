<img src="http://sjackman.ca/img/tigmint.png" style="width:4in">

# Correct misassemblies using Linked Reads

Split sequences at positions with a low number of spanning molecules 

Written by [Shaun Jackman](http://sjackman.ca).

# Description

Tigmint identifies and corrects misassemblies using linked reads from 10x Genomics Chromium. The reads are first aligned to the assembly, and the extents of the large DNA molecules are inferred from the alignments of the reads. The physical coverage of the large molecules is more consistent and less prone to coverage dropouts than that of the short read sequencing data. Each scaffold is scanned with a fixed window to identify areas where there are few spanning molecules, revealing possible misassemblies. Scaffolds are cut where spanning molecules are identified following windows with no spanning molecules. 

# Installation

Download and extract the source code. Compiling is not needed.

```
git clone https://github.com/bcgsc/tigmint && cd tigmint
```
or
```
curl -L https://github.com/bcgsc/tigmint/archive/master.tar.gz | tar xz && mv tigmint-master tigmint && cd tigmint
```

# Dependencies

Dependencies may be installed using [Homebrew](https://brew.sh) on macOS or [Linuxbrew](http://linuxbrew.sh) on Linux.

## Install the dependencies of Tigmint
Python requirements: Python 3.4+, pybedtools (https://daler.github.io/pybedtools/), intervaltree (https://github.com/chaimleib/intervaltree)
```sh
brew tap homebrew/science
brew install bedtools bwa gawk gnu-sed miller pigz r samtools seqtk
Rscript -e 'install.packages(c("ggplot2", "rmarkdown", "tidyverse", "uniqtag"))'
```

## Install the dependencies of ARCS (optional)
```sh
brew install arcs links-scaffolder
```

## Install the dependencies for calculating assembly metrics (optional)
```sh
brew install abyss
```

# Usage


To run Tigmint on the draft assembly `myassembly.fa` with the reads `myreads.fq.gz`, which have been run through `longranger basic`:

```sh
tigmint-make tigmint draft=myassembly reads=myreads
```

To run both Tigmint and scaffold the corrected assembly with [ARCS](https://github.com/bcgsc/arcs):

```sh
tigmint-make arcs draft=myassembly reads=myreads
```

To run Tigmint, ARCS, and calculate assembly metrics using the reference genome `GRCh38.fa`:

```sh
tigmint-make metrics draft=myassembly reads=myreads ref=GRCh38 G=3088269832
```

# Note

+ `tigmint-make` is a Makefile script, and so any `make` options may also be used with `tigmint-make`, such as `-n` (`--dry-run`).
+ The file extension of the assembly must be `.fa` and the reads `.fq.gz`, and the extension is not included in the parameters `draft` and `reads`. These specific file name requirements result from implementing the pipeline in GNU Make.

# Commands

+ `tigmint`: Run Tigmint, and produce a file named `$draft.tigmint.fa`
+ `arcs`: Run Tigmint and ARCS, and produce a file name `$draft.tigmint.arcs.fa`
+ `metrics`: Run, Tigmint, ARCS, and calculate assembly metrics using `abyss-fac` and `abyss-samtobreak`, and produce TSV files.

# Parameters of Tigmint

+ `draft`: Name of the draft assembly, `draft.fa`
+ `reads`: Name of the reads, `reads.fq.gz`
+ `span=2`: Number of spanning molecules threshold
+ `minsize=2000`: Minimum molecule size
+ `as=0.65`: Minimum AS/read length ratio
+ `nm=5`: Maximum number of mismatches
+ `trim=0`: Number of bases to trim off contigs following cuts
+ `t=8`: Number of threads
+ `gzip=gzip`: gzip compression program, use `pigz -p8` for parallelized compression

# Parameters of ARCS
+ `c=5`
+ `e=30000`
+ `r=0.05`

# Parameters of LINKS
+ `a=0.1`
+ `l=10`

# Parameters for calculating assembly metrics

+ `ref`: Reference genome, `ref.fa`, for calculating assembly contiguity metrics
+ `G`: Size of the reference genome, for calculating NG50 and NGA50

# Support

After first looking for existing issue at <https://github.com/bcgsc/tigmint/issues>, please report a new issue at <https://github.com/bcgsc/tigmint/issues/new>. Please report the names of your input files, the exact command line that you are using, and the entire output of `tigmint-make`.

# Pipeline

[![Tigmint pipeline illustration](pipeline.gv.png)](pipeline.gv.svg)

[Makefile](tigmint-make) &middot; [CWL](tigmint-make.cwl) &middot; [CWLViewer](https://view.commonwl.org/workflows/github.com/bcgsc/tigmint/tree/master/tigmint-make.cwl)

[![Tigmint pipeline Makefile](tigmint-make.gv.png)](tigmint-make.gv.svg)
