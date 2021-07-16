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
newb change-table
	cmt Alter the existing tables
newb drop-location-type
	cmt Drop location type from models

git checkout develop
newb edit-margin-not-allowed
	cmt Disallow editing margin
newb full-load-gatling
	cmt Implement Gatling full load scenario

git checkout develop
newb grep-errors-script
	cmt Add script for grepping the errors

git checkout root
newb master
	cmt Master commit
newb hotfix/remove-trigger
	cmt HOTFIX Remove the trigger

cat >.git/machete <<EOF
develop
    adjust-reads-prec
        block-cancel-order
            change-table
                drop-location-type
    edit-margin-not-allowed
        full-load-gatling
    grep-errors-script
master
    hotfix/remove-trigger
EOF

# Let's spoil sth...
git checkout develop
cmt Other develop commit
git checkout adjust-reads-prec
cmt 1st round of fixes
cmt 2nd round of fixes
git checkout change-table
cmt 1st round of fixes

git branch -d root

echo
echo
git machete status $1
echo
echo

