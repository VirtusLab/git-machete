#!/usr/bin/env awk

BEGIN { exit_code = 0 }

FNR == 1 { prev_is_unsafe_terminated_string = 0 }

prev_is_unsafe_terminated_string && /^ *f?["'][^ ]/ {
  print FILENAME ":" FNR-1 "-" FNR ": it looks that the string is split without a delimiter, words will be glued up together when printed"
  print ""
  print prev
  print $0
  print "\n"
  exit_code = 1
}

                 { prev_is_unsafe_terminated_string = 0 }

/[^ ]["'] *\\?$/ { prev_is_unsafe_terminated_string = 1 }

/\\n["'] *\\?$/  { prev_is_unsafe_terminated_string = 0 }

{ prev = $0 }

END { exit exit_code }
