# Requires GNU awk (gawk) due to the use of |&

function trailer(v) {
  "git log -1 --date=rfc2822 --format=%cd v" v " 2>/dev/null || date --rfc-email" |& getline date
  printf "\n -- Pawel Lipski <plipski@virtuslab.com>  %s\n\n\n", date
}

/## New in git-machete .*/ {
  if (version) {
    trailer(version)
  }
  match($0, /[0-9.]+/)
  newVersion = substr($0, RSTART, RLENGTH)
  version = newVersion
  print "python3-git-machete (" version "~" distro_number ") " distro_name "; urgency=medium\n"
}

/^- / {
  gsub("^- ", "  * ")
  print $0
}

END { trailer(version) }
