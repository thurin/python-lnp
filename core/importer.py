#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Import user content from an old DF or Starter Pack install.

The content to import is defined in PyLNP.json

Two import strategies are currently supported:

:copy_add:
    copy a file or directory contents, non-recursive, no overwriting
:text_prepend:
    prepend imported file content (for logfiles)


These strategies support the 'low hanging fruit' of imports.  Other content
or more advanced strategies have been identified, but are difficult to
implement without risking a 'bad import' scenario:

:init files:
    Not simply copyable. Sophisticated merging (similar to graphics
    upgrades) may lead to bad config when using settings from an older
    version of DF.  Will not be supported.
:keybinds:
    Could be imported by minimising interface.txt (and ``LNP/Keybinds/*``)
    (see core/keybinds.py), and copying if a duplicate set is not yet
    available.  Planned for future update.
:world_gen, embark_profiles:
    Importing world gen and embark profiles may be supported eventually.
    No obvious downsides beyond tricky implementation.
:other:
    Custom settings importer - eg which graphics pack, are aquifers
    disabled, other PyLNP settings...  May be added later but no plans.

"""
from __future__ import print_function, unicode_literals, absolute_import

import os
import shutil

from . import log, paths
from .lnp import lnp


def strat_fallback(strat):
    """Log error if an unknown strategy is attempted."""
    def __fallback(src, dest):
        #pylint:disable=unused-argument
        log.w('Attempted to use unknown strategy ' + strat)
        return False
    return __fallback


def strat_copy_add(src, dest):
    """Copy a file or directory contents from src to dest, without overwriting.
    If a single file, an existing file may be overwritten if it only contains
    whitespace.  For directory contents, only the top level is 'filled in'.
    """
    # handle the simple case, one file
    if os.path.isfile(src):
        if os.path.isfile(dest):
            with open(dest) as f:
                if f.read().strip():
                    log.i('Skipping import of {} to {}; dest is non-empty file'
                          .format(src, dest))
                    return False
        log.i('importing {} to {} by copying'.format(src, dest))
        shutil.copy2(src, dest)
        return True
    # adding dir contents
    ret = False
    for it in os.listdir(src):
        if os.path.exists(os.path.join(dest, it)):
            log.i('Skipping import of {}/{}, exists in dest'.format(src, it))
            continue
        ret = True  # *something* was imported
        log.i('importing {} from {} to {}'.format(it, src, dest))
        if not os.path.isdir(dest):
            os.makedirs(dest)
        item = os.path.join(src, it)
        if os.path.isfile(item):
            shutil.copy2(item, dest)
        else:
            shutil.copytree(item, os.path.join(dest, it))
    return ret


def strat_text_prepend(src, dest):
    """Prepend the src textfile to the dest textfile, creating it if needed."""
    if not os.path.isfile(src):
        log.i('Cannot import {} - not a file'.format(src))
        return False
    if not os.path.isfile(dest):
        log.i('importing {} to {} by copying'.format(src, dest))
        shutil.copy2(src, dest)
        return True
    with open(src, encoding='latin1') as f:
        srctext = f.read()
    with open(dest, encoding='latin1') as f:
        desttext = f.read()
    with open(src, 'w', encoding='latin1') as f:
        log.i('importing {} to {} by prepending'.format(src, dest))
        f.writelines([srctext, '\n', desttext])
    return True


def do_imports(from_df_dir):
    """Import content (defined in PyLNP.json) from the given previous df_dir,
    and associated LNP install if any.
    """
    # pylint:disable=too-many-locals,too-many-branches
    # validate that from_df_dir is, in fact, a DF dir
    if not all(os.path.exists(os.path.join(from_df_dir, *p)) for p in
               [('data', 'init', 'init.txt'), ('raw', 'objects')]):
        return (False, 'Does not seem to be a DF install directory.')
    # Get list of paths, and add dest where implicit (ie same as src)
    if not lnp.config.get('to_import'):
        return (False, 'Nothing is configured for import in PyLNP.json')
    raw_config = [(c + [c[1]])[:3] for c in lnp.config['to_import']]

    path_pairs = []
    # Turn "paths" in PyLNP.json into real paths
    for st, src, dest in raw_config:
        if '<df>' in src:
            newsrc = src.replace('<df>', from_df_dir)
        else:
            newsrc = os.path.join(from_df_dir, '../', src)
        newsrc = os.path.abspath(os.path.normpath(newsrc))
        if '<df>' in dest:
            newdest = dest.replace('<df>', paths.get('df'))
        else:
            newdest = paths.get('root', dest)
        newdest = os.path.abspath(os.path.normpath(newdest))
        path_pairs.append((st, newsrc, newdest))

    # Sanity-check the provided paths...
    src_prefix = os.path.commonprefix([src for _, src, _ in path_pairs])
    dest_prefix = os.path.commonprefix([dest for _, _, dest in path_pairs])
    log.i('Importing from {} to {}'.format(src_prefix, dest_prefix))
    if not (os.path.isdir(src_prefix) or os.path.dirname(src_prefix)):
        # parent dir is a real path, even when os.path.commonprefix isn't
        msg = 'Can only import content from single basedir'
        log.w(msg)
        return (False, msg)
    if not dest_prefix:
        # checking <base>.startswith avoids the os.path.commonprefix issue
        msg = 'Can only import content to destinations below current basedir'
        log.w(msg)
        return (False, msg)

    strat_funcs = {
        'copy_add': strat_copy_add,
        'text_prepend': strat_text_prepend,
        }
    imported = []
    for strat, src, dest in path_pairs:
        if not os.path.exists(src):
            log.w('Cannot import {} - does not exist'.format(src))
            continue
        if strat_funcs.get(strat, strat_fallback(strat))(src, dest):
            imported.append(src)
    if not imported:
        return (False, 'Nothing was found to import!')
    return (True, '\n'.join(imported))
