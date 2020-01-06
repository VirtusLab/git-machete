import io
import os
import random
import re
import string
import sys
import textwrap
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
            os.system('git init %s' % opt)
        else:
            os.system('git init')
        return self

    def new_branch(self, branch_name):
        os.system('git checkout -b %s' % branch_name)
        return self

    def commit(self, *args):
        f = '%s.txt' % "".join(random.choice(string.ascii_letters) for i in range(20))
        os.system('touch %s' % f)
        os.system('git add %s' % f)
        os.system('git commit -m "%s"' % ("".join(args)))
        return self

    def push(self):
        branch = os.popen('git symbolic-ref --short HEAD').read()
        os.system('git push -u origin %s' % branch)
        return self

    def checkout(self, branch):
        os.system('git checkout %s' % branch)
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
        os.system('git commit --amend -m "HOTFIX Add the trigger (amended)"')
        machete_string = """
            develop
                allow-ownership-link PR #123
                    build-chain PR #124
                call-ws
            master
                hotfix/add-trigger
        """
        with open('.git/machete', "w+") as definition_file:
            definition_file.writelines(textwrap.dedent(machete_string))
        os.system('git branch -d root')

        out = io.StringIO()
        sys.stdout = out
        cmd.launch(['git-machete', 'status'])
        return out.getvalue()


Setup = SandboxSetup()


def adapt(s):
    return re.sub(r"\|\n", "| \n", s[1:])


expected_output = adapt("""
  develop
  |
  x-allow-ownership-link  PR #123 (ahead of origin)
  | |
  | x-build-chain  PR #124 (untracked)
  |
  o-call-ws (ahead of origin)

  master
  |
  o-hotfix/add-trigger * (diverged from origin)
""")


class MacheteTester(unittest.TestCase):

    def test_machete(self):
        self.assertEqual(Setup.setup_sandbox(), expected_output)
