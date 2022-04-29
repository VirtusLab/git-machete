#!/usr/bin/env awk

BEGIN { exit_code = 0 }

FNR == 1 { prev_non_empty = "" }

( prev_non_empty !~  /^ {2}/ &&  /^ {3}/ ) ||
( prev_non_empty !~  /^ {4}/ &&  /^ {5}/ ) ||
( prev_non_empty !~  /^ {6}/ &&  /^ {7}/ ) ||
( prev_non_empty !~  /^ {8}/ &&  /^ {9}/ ) ||
( prev_non_empty !~ /^ {10}/ && /^ {11}/ ) {
  print FILENAME ":" FNR ": likely three or four spaces used for indent instead of two"
  exit_code = 1
}

/^.+$/ { prev_non_empty = $0 }

END { exit exit_code }
