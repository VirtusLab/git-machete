BEGIN {
    in_testenv = 0
    deps_defined = 0
    missing_deps_envs = ""
    count_missing = 0
}

/^\[testenv(:[^\]]+)?\]/ {
    # If we were inside a previous testenv, check if deps were missing
    if (in_testenv && deps_defined == 0) {
        missing_deps_envs = missing_deps_envs env_name "\n"
        count_missing++
    }
    # Start new testenv block
    in_testenv = 1
    deps_defined = 0
    env_name = $0
    next
}

in_testenv && /^[[:space:]]*deps[[:space:]]*=/ {
    deps_defined = 1
}

# If we hit a new section that is not testenv, close previous testenv block
/^\[/ && !/^\[testenv(:[^\]]+)?\]/ {
    if (in_testenv && deps_defined == 0) {
        missing_deps_envs = missing_deps_envs env_name "\n"
        count_missing++
    }
    in_testenv = 0
    env_name = ""
    deps_defined = 0
}

END {
    # Check last testenv block if file ended inside it
    if (in_testenv && deps_defined == 0) {
        missing_deps_envs = missing_deps_envs env_name "\n"
        count_missing++
    }

    if (count_missing > 0) {
        print "The following [testenv:...] environments do NOT define their own 'deps =' and inherit from [testenv], which is usually unintended:" > "/dev/stderr"
        printf "%s", missing_deps_envs > "/dev/stderr"
        exit 1
    }
    exit 0
}
