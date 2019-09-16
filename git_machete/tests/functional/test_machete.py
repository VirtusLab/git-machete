import io
import os
import random
import re
from six import u as unicode
import string
import sys
import unittest

from git_machete import cmd


class SandboxSetup:

    def __init__(self):
        self.file_dir = os.path.dirname(os.path.abspath(__file__))
        self.remote_path = os.popen('mktemp -d').read().strip()
        self.sandbox_path = os.popen('mktemp -d').read().strip()

    def new_repo(self, *args):
        os.chdir(args[0])
        if len(args) > 1:
            opt = args[1]
            os.system('git init -q %s' % opt)
        else:
            os.system('git init -q')
        return self

    def new_branch(self, branch_name):
        os.system('git checkout -q -b %s' % branch_name)
        return self

    def commit(self, *args):
        f = '%s.txt' % "".join(random.choice(string.ascii_letters) for i in range(20))
        os.system('touch %s' % f)
        os.system('git add %s' % f)
        os.system('git commit -q -m "%s"' % ("".join(args)))
        return self

    def push(self):
        branch = os.popen('git symbolic-ref --short HEAD').read()
        os.system('git push -q -u origin %s' % branch)
        return self

    def checkout(self, branch):
        os.system('git checkout -q %s' % branch)
        return self

    def setup_sandbox(self):
        self.new_repo(self.remote_path, '--bare')
        self.new_repo(self.sandbox_path)
        os.system('git remote add origin %s' % self.remote_path)
        self.new_branch('root')
        os.system('git config user.email "tester@test.com"')
        os.system('git config user.name "Tester Test"')
        self.commit('root') \
            .new_branch('develop') \
            .commit('develop commit') \
            .new_branch('allow-ownership-link') \
            .commit('Allow ownership links') \
            .push() \
            .new_branch('build-chain') \
            .commit('Build arbitrarily long chains') \
            .checkout('allow-ownership-link') \
            .commit('1st round of fixes') \
            .checkout('develop') \
            .commit('Other develop commit') \
            .push() \
            .new_branch('call-ws') \
            .commit('Call web service') \
            .commit('1st round of fixes') \
            .push() \
            .new_branch('drop-constraint') \
            .commit('Drop unneeded SQL constraints') \
            .checkout('call-ws') \
            .commit('2nd round of fixes') \
            .checkout('root') \
            .new_branch('master') \
            .commit('Master commit') \
            .push() \
            .new_branch('hotfix/add-trigger') \
            .commit('HOTFIX Add the trigger') \
            .push()
        os.system('git commit -q --amend -m "HOTFIX Add the trigger (amended)"')
        os.system('git branch -d root')


Setup = SandboxSetup()


def adapt(s):
    return re.sub(r"\|\n", "| \n", s[1:])


expected_status_1 = adapt("""
  develop
  |
  x-allow-ownership-link (ahead of origin)
  | |
  | x-build-chain (untracked)
  |
  o-call-ws (ahead of origin)
    |
    x-drop-constraint (untracked)

  master
  |
  o-hotfix/add-trigger * (diverged from origin)
""")

expected_status_l_2 = adapt("""
  develop
  |
  | Allow ownership links
  | 1st round of fixes
  o-allow-ownership-link
  | |
  | | Build arbitrarily long chains
  | o-build-chain
  |
  | Call web service
  | 1st round of fixes
  | 2nd round of fixes
  o-call-ws
    |
    | Drop unneeded SQL constraints
    o-drop-constraint

  master
  |
  | HOTFIX Add the trigger (amended)
  o-hotfix/add-trigger *
""")


class StringIOWrapper:
    def __init__(self):
        self.io = io.StringIO()

    def isatty(self):
        return False

    def write(self, s):
        if type(s).__name__ == 'unicode':
            self.io.write(s)  # Python 2
        else:
            self.io.write(unicode(s))  # Python 2/3

    def getvalue(self):
        return self.io.getvalue()


class MacheteTester(unittest.TestCase):

    @staticmethod
    def launch_command(*args):
        orig_out = sys.stdout
        out = StringIOWrapper()
        sys.stdout = out
        try:
            cmd.launch(args)
        finally:
            sys.stdout = orig_out
        return out.getvalue()

    def test_status_traverse_status(self):
        Setup.setup_sandbox()
        self.launch_command('discover', '-y', '--roots=develop,master')
        self.assertEqual(self.launch_command('status'), expected_status_1)
        self.launch_command('traverse', '-Wy')
        self.assertEqual(self.launch_command('status', '-l'), expected_status_l_2)
