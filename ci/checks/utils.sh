function error() {
  red='\033[91m'
  endc='\033[0m'

  if [[ $# -ge 1 ]]; then
    if [[ -t 1 ]]; then
      echo -e "${red}>>> $* <<<${endc}"
    else
      echo -e ">>> $* <<<"
    fi
  fi
}

function die() {
  echo
  error "$@"
  echo
  exit 1
}
