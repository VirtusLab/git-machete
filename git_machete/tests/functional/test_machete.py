import io
import os
import random
import re
import string
import sys
import time
import unittest

from git_machete import cmd


class SandboxSetup:

    def __init__(self):
        self.file_dir = os.path.dirname(os.path.abspath(__file__))
        self.remote_path = os.popen('mktemp -d').read().strip()
        self.sandbox_path = os.popen('mktemp -d').read().strip()

    @staticmethod
    def execute(command):
        result = os.system(command)
        assert result == 0, "%s returned %i" % (command, result)

    def new_repo(self, *args):
        os.chdir(args[0])
        if len(args) > 1:
            opt = args[1]
            self.execute('git init %s' % opt)
        else:
            self.execute('git init')
        return self

    def new_branch(self, branch_name):
        self.execute('git checkout -q -b %s' % branch_name)
        return self

    def check_out(self, branch):
        self.execute('git checkout -q %s' % branch)
        return self

    def commit(self, message):
        f = '%s.txt' % "".join(random.choice(string.ascii_letters) for i in range(20))
        self.execute('touch %s' % f)
        self.execute('git add %s' % f)
        self.execute('git commit -q -m "%s"' % message)
        return self

    def commit_amend(self, message):
        self.execute('git commit -q --amend -m "%s"' % message)
        return self

    def push(self):
        branch = os.popen('git symbolic-ref --short HEAD').read()
        self.execute('git push -q -u origin %s' % branch)
        return self

    def sleep(self, seconds):
        time.sleep(seconds)
        return self

    def reset_to(self, revision):
        self.execute('git reset --keep "%s"' % revision)
        return self

    def delete_branch(self, branch):
        self.execute('git branch -d "%s"' % branch)
        return self

    def setup_sandbox(self):
        self.new_repo(self.remote_path, '--bare')
        self.new_repo(self.sandbox_path)
        self.execute('git remote add origin %s' % self.remote_path)
        self.execute('git config user.email "tester@test.com"')
        self.execute('git config user.name "Tester Test"')
        self.new_branch('root') \
            .commit('root') \
            .new_branch('develop') \
            .commit('develop commit') \
            .new_branch('allow-ownership-link') \
            .commit('Allow ownership links') \
            .push() \
            .new_branch('build-chain') \
            .commit('Build arbitrarily long chains') \
            .check_out('allow-ownership-link') \
            .commit('1st round of fixes') \
            .check_out('develop') \
            .commit('Other develop commit') \
            .push() \
            .new_branch('call-ws') \
            .commit('Call web service') \
            .commit('1st round of fixes') \
            .push() \
            .new_branch('drop-constraint') \
            .commit('Drop unneeded SQL constraints') \
            .check_out('call-ws') \
            .commit('2nd round of fixes') \
            .check_out('root') \
            .new_branch('master') \
            .commit('Master commit') \
            .push() \
            .new_branch('hotfix/add-trigger') \
            .commit('HOTFIX Add the trigger') \
            .push() \
            .commit_amend('HOTFIX Add the trigger (amended)') \
            .new_branch('ignore-trailing') \
            .commit('Ignore trailing data') \
            .sleep(1) \
            .commit_amend('Ignore trailing data (amended)') \
            .push() \
            .reset_to('ignore-trailing@{1}') \
            .delete_branch('root')


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
  o-hotfix/add-trigger (diverged from origin)
    |
    o-ignore-trailing * (diverged from & older than origin)
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
  o-hotfix/add-trigger
    |
    | Ignore trailing data (amended)
    o-ignore-trailing *
""")


class MacheteTester(unittest.TestCase):

    @staticmethod
    def launch_command(*args):
        orig_out = sys.stdout
        out = io.StringIO()
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
