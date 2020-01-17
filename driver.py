#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from git_machete import cmd
from pyannotate_runtime import collect_types
import os

DEBUG = False
json_name = 'type_info.json'
file_dir = os.path.dirname(os.path.abspath(__file__))


def del_json():
    os.remove(json_name)


def create_types():
    os.system('pyannotate -w ./git_machete/cmd.py')


commands = [
    'status',
    'file',
    'add --yes',
    'anno',
    'discover --yes',
    'delete-unmanaged',
    'go',
    'list',
    'show',
    'diff',
    'fork-point',
    'log',
    'slide-out --no-interactive-rebase',
    'traverse --no-interactive-rebase',
    'update --no-interactive-rebase',
    '--version'
]


def main():

    collect_types.init_types_collection()
    with collect_types.collect():
        os.chdir('/home/maciej/Desktop/REPO')
        for c in commands:
            coms = c.split(' ')
            # coms.insert(0,'')
            try:
                if 'add' in coms:
                    os.system('mv .git/machete .git/machete_del')
                if 'update' in coms:
                    os.system('mv .git/machete_del .git/machete')
                cmd.launch(coms)
            except SystemExit:
                pass

    os.chdir(file_dir)
    collect_types.dump_stats(json_name)

    if DEBUG:
        if os.path.exists(json_name):
            print('\n\n\n\n\nSuccessfully created type_info.json')
            # del_json()
        else:
            print('An error occured')
    else:
        create_types()
        del_json()
        print('Successfully created types')


if __name__ == "__main__":
    main()
