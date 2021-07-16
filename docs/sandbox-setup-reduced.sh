#!/usr/bin/env bash

newb() {
	git checkout -b $1
}

cmt() {
	b=$(git symbolic-ref --short HEAD)
	f=${b/\//-}-${1}-${2}.txt
	touch $f
	git add $f
	git commit -m "$*"
}

dir=~/machete-sandbox
mkdir -p $dir
cd $dir
rm -fr /tmp/_git
mv .git /tmp/_git
rm -f ./*
git init

newb root
	cmt Root
newb develop
	cmt Develop commit
newb adjust-reads-prec
	cmt Adjust JSON Reads precision
newb block-cancel-order
	cmt Implement blocking order cancellation
git checkout adjust-reads-prec
	cmt 1st round of fixes

git branch -d root

