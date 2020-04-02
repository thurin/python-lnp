#!/usr/bin/env python
# -*- coding: utf-8 -*-
# pylint:disable=unused-wildcard-import,wildcard-import,invalid-name,too-many-instance-attributes,too-many-public-methods,too-many-statements
"""TKinter-based GUI for PyLNP."""
from __future__ import print_function, unicode_literals, absolute_import

import os
import sys
from threading import Semaphore

from core.helpers import get_resource
from core.lnp import lnp, VERSION
from core import df, launcher, log, paths, update, mods, download, baselines
from core import terminal, importer

from . import controls, binding
from .child_windows import LogWindow, InitEditor, SelectDF, UpdateWindow
from .child_windows import ConfirmRun, TerminalSelector

from .options import OptionsTab
from .graphics import GraphicsTab
from .utilities import UtilitiesTab
from .advanced import AdvancedTab
from .dfhack import DFHackTab
from .mods import ModsTab

if sys.version_info[0] == 3:  # Alternate import names
    # pylint:disable=import-error
    import queue as Queue
    from tkinter import *
    from tkinter.ttk import *
    import tkinter.messagebox as messagebox
    import tkinter.filedialog as filedialog
    import tkinter.font as tkFont
    #pylint:disable=redefined-builtin
    basestring = str
else:
    # pylint:disable=import-error
    import Queue
    from Tkinter import *
    from ttk import *
    import tkMessageBox as messagebox
    import tkFileDialog as filedialog
    import tkFont

# Workaround to use Pillow in PyInstaller
if False: # pylint:disable=using-constant-test
    # pylint:disable=unused-import
    import pkg_resources

try:  # PIL-compatible library (e.g. Pillow); used to load PNG images (optional)
    # pylint:disable=import-error,no-name-in-module
    from PIL import Image, ImageTk
    has_PIL = True
except ImportError:  # Some PIL installations live outside of the PIL package
    # pylint:disable=import-error,no-name-in-module
    try:
        import Image
        import ImageTk
        has_PIL = True
    except ImportError:  # No PIL compatible library
        has_PIL = False

has_PNG = has_PIL or (TkVersion >= 8.6)  # Tk 8.6 supports PNG natively

if not has_PIL:
    log.w("No PIL support available - cannot perform image manipulation")
if not has_PNG:
    log.w(
        'Note: PIL not found and Tk version too old for PNG support (%s).'
        'Falling back to GIF images.', TkVersion)


def get_image(filename):
    """
    Open the image with the appropriate extension.

    Args:
        filename: The base name of the image file.

    Returns:
        A PhotoImage object ready to use with Tkinter.
    """
    if has_PNG:
        filename = filename + '.png'
    else:
        filename = filename + '.gif'
    try:
        if has_PIL:
            # pylint:disable=maybe-no-member
            return ImageTk.PhotoImage(Image.open(filename))
        else:
            return PhotoImage(file=filename)
    except: # pylint:disable=bare-except
        log.w('Unable to load image: ' + filename)

def validate_number(value_if_allowed):
    """
    Validation method used by Tkinter. Accepts empty and float-coercable
    strings.

    Args:
        value_if_allowed: Value to validate.

    Returns:
        True if value_if_allowed is empty, or can be interpreted as a float.
    """
    if value_if_allowed == '':
        return True
    try:
        float(value_if_allowed)
        return True
    except ValueError:
        return False

def fixed_map(option):
    # Fix for setting text colour for Tkinter 8.6.9
    # From: https://core.tcl.tk/tk/info/509cafafae
    #
    # Returns the style map for 'option' with any styles starting with
    # ('!disabled', '!selected', ...) filtered out.

    # style.map() returns an empty list for missing options, so this
    # should be future-safe.
    return [elm for elm in Style().map('Treeview', query_opt=option) if
            elm[:2] != ('!disabled', '!selected')]

class TkGui(object):
    """Main GUI window."""
    def __init__(self):
        """
        Constructor for TkGui.

        Args:
            lnp: A PyLNP instance to perform actual work.
        """
        self.root = root = Tk()
        self.updateDays = IntVar()
        self.downloadBaselines = BooleanVar()
        self.show_scrollbars = BooleanVar()
        self.autoclose = BooleanVar()
        self.do_reload = False
        controls.init(self)
        binding.init(lnp, self)

        if not self.ensure_df():
            return

        if sys.version_info[0] == 3:
            Style().map('Treeview', foreground=fixed_map('foreground'),
                        background=fixed_map('background'))

        if lnp.os == 'linux' and not terminal.terminal_configured():
            self.root.withdraw()
            messagebox.showinfo(
                'PyLNP',
                'You need to configure a terminal to allow things like DFHack '
                'to work correctly. Press OK to do this now.')
            self.configure_terminal(True)
            self.root.deiconify()

        root.option_add('*tearOff', FALSE)
        windowing = root.tk.call('tk', 'windowingsystem')
        if windowing == "win32":
            root.tk.call(
                'wm', 'iconbitmap', root, "-default",
                get_resource('LNP.ico'))
        elif windowing == "x11":
            root.tk.call(
                'wm', 'iconphoto', root, "-default",
                get_image(get_resource('LNP')))
        elif windowing == "aqua":  # OS X has no window icons
            pass

        root.title("PyLNP")
        self.vcmd = (root.register(validate_number), '%P')

        main = Frame(root)
        self.logo = logo = get_image(get_resource('LNPSMALL'))
        Label(root, image=logo, anchor=CENTER).pack(fill=X)
        main.pack(side=TOP, fill=BOTH, expand=Y)

        self.download_panel = controls.create_control_group(
            main, 'Download status')
        self.download_text = StringVar()
        self.download_status = Label(
            self.download_panel, textvariable=self.download_text)
        self.download_panel.pack(fill=X, expand=N, side=BOTTOM)
        self.download_status.pack(side=BOTTOM)

        self.n = n = Notebook(main)

        self.create_tab(OptionsTab, 'Options')
        self.create_tab(GraphicsTab, 'Graphics')
        self.create_tab(UtilitiesTab, 'Utilities')
        self.create_tab(AdvancedTab, 'Advanced')
        if 'dfhack' in lnp.df_info.variations:
            self.create_tab(DFHackTab, 'DFHack')
        if mods.read_mods():
            self.create_tab(ModsTab, 'Mods')
        n.enable_traversal()
        n.pack(fill=BOTH, expand=Y, padx=2, pady=3)

        play_font = tkFont.Font(font='TkDefaultFont')
        play_font.config(weight=tkFont.BOLD, size=int(play_font['size'] * 1.5))
        Style().configure('Big.TButton', font=play_font)
        play_button = controls.create_trigger_button(
            main, 'Play Dwarf Fortress!', 'Play the game!', self.run_df)
        if sys.platform != 'darwin':
            play_button.configure(style='Big.TButton')
            play_button.pack(side=BOTTOM, fill=X, padx=(1, 3), pady=(0, 3))
        else:
            play_button.pack(side=BOTTOM, fill=X, padx=(30, 30), pady=(0, 3))

        self.menubar = self.create_menu(root)

        self.save_size = None
        root.update()
        height = root.winfo_height()
        if windowing == "x11":
            # On Linux, the menu bar height isn't being calculated correctly
            # for minsize
            height += self.menubar.winfo_reqheight()
        root.minsize(width=root.winfo_width(), height=height)
        self.download_panel.pack_forget()
        root.geometry('{}x{}'.format(
            lnp.userconfig.get_number('tkgui_width'),
            lnp.userconfig.get_number('tkgui_height')))
        root.bind("<Configure>", lambda e: self.on_resize())
        root.update()

        queue = download.get_queue('baselines')
        queue.register_start_queue(self.start_download_queue)
        queue.register_begin_download(self.start_download)
        queue.register_progress(self.download_progress)
        queue.register_end_download(self.end_download)
        queue.register_end_queue(self.end_download_queue)

        binding.update()
        root.bind('<<UpdateAvailable>>', lambda e: UpdateWindow(self.root))

        # Used for cross-thread signaling and communication during downloads
        self.update_pending = Semaphore(1)
        self.queue = Queue.Queue()
        self.cross_thread_data = None
        self.reply_semaphore = Semaphore(0)
        self.download_text_string = ''
        root.bind('<<ConfirmDownloads>>', lambda e: self.confirm_downloading())
        root.bind('<<ForceUpdate>>', lambda e: self.update_download_text())
        root.bind('<<ShowDLPanel>>', lambda e: self.download_panel.pack(
            fill=X, expand=N, side=BOTTOM))
        root.bind(
            '<<HideDLPanel>>', lambda e: self.download_panel.pack_forget())
        self.cross_thread_timer = self.root.after(100, self.check_cross_thread)

    def on_resize(self):
        """Called when the window is resized."""
        lnp.userconfig['tkgui_width'] = self.root.winfo_width()
        lnp.userconfig['tkgui_height'] = self.root.winfo_height()
        if self.save_size:
            self.root.after_cancel(self.save_size)
        self.save_size = self.root.after(1000, lnp.userconfig.save_data)

    def start(self):
        """Starts the UI."""
        self.root.mainloop()
        if self.do_reload:
            lnp.reload_program()

    def on_update_available(self):
        """Called by the main LNP class if an update is available."""
        self.queue.put('<<UpdateAvailable>>')

    def on_program_running(self, path, is_df):
        """Called by the main LNP class if a program is already running."""
        ConfirmRun(self.root, path, is_df)

    @staticmethod
    def on_invalid_config(errors):
        """Notifies a user about an invalid configuration."""
        return messagebox.askyesno(
            message='Some problems were found with your current '
            'configuration:\n\n' + '\n'.join(errors) + '\n\nRun DF anyway?',
            title='Invalid configuration', icon='warning', default='no')

    def on_request_update_permission(self, interval):
        """Asks the user if update checking should be performed."""
        if interval == 0:
            days = 'launch'
        elif interval == 1:
            days = 'day'
        else:
            days = str(interval)+' days'
        result = messagebox.askyesno(
            message='This pack can automatically check for updates. The author '
            'of this pack suggests checking every '+days+'.\n\nAllow automatic '
            'update checks? You can change this behavior at any time from '
            'Options > Check for Updates.', title='Update checks',
            icon='question', default='yes')
        if result:
            self.updateDays.set(interval)
        else:
            self.updateDays.set(-1)

    def create_tab(self, class_, caption):
        """
        Creates a new tab and adds it to the main Notebook.

        Args:
            ``class_``: Reference to the class representing the tab.
            caption: Caption for the newly created tab.
        """
        tab = class_(self.n, pad=(4, 2))
        self.n.add(tab, text=caption)

    def ensure_df(self):
        """Ensures a DF installation is active before proceeding."""
        if paths.get('df') == '':
            self.root.withdraw()
            if lnp.folders:
                selector = SelectDF(self.root, lnp.folders)
                if selector.result == '':
                    messagebox.showerror(
                        'PyLNP',
                        'No Dwarf Fortress install was selected, quitting.')
                    self.root.destroy()
                    return False
                else:
                    try:
                        df.set_df_folder(selector.result)
                    except IOError as e:
                        messagebox.showerror(self.root.title(), str(e))
                        self.exit_program()
                        return False
            else:
                messagebox.showerror(
                    'PyLNP',
                    "Could not find Dwarf Fortress, quitting.")
                self.root.destroy()
                return False
            self.root.deiconify()
        return True

    def create_menu(self, root):
        """
        Creates and returns the menu bar.

        Args:
            root: Root window for the menu bar.
        """
        menubar = Menu(root, type='menubar')
        root['menu'] = menubar

        menu_file = Menu(menubar)
        menu_options = Menu(menubar)
        menu_run = Menu(menubar)
        menu_folders = Menu(menubar)
        menu_links = Menu(menubar)
        menu_help = Menu(menubar)
        #menu_beta = Menu(menubar)
        menubar.add_cascade(menu=menu_file, label='File')
        menubar.add_cascade(menu=menu_options, label='Options')
        menubar.add_cascade(menu=menu_run, label='Run')
        menubar.add_cascade(menu=menu_folders, label='Folders')
        menubar.add_cascade(menu=menu_links, label='Links')
        menubar.add_cascade(menu=menu_help, label='Help')
        #menubar.add_cascade(menu=menu_beta, label='Testing')

        menu_file.add_command(
            label='Re-load param set', command=self.load_params,
            accelerator='Ctrl+L')
        menu_file.add_command(
            label='Re-save param set', command=self.save_params,
            accelerator='Ctrl+S')
        menu_file.add_command(
            label='Output log', command=lambda: LogWindow(self.root))

        menu_file.add_command(
            label='Restore default settings', command=self.restore_defaults)

        if sys.platform.startswith('linux'):
            menu_file.add_command(
                label="Configure terminal...", command=self.configure_terminal)

        if len(lnp.folders) > 1:
            menu_file.add_command(
                label="Reload/Choose DF folder", command=self.reload_program)

        menu_file.add_command(
            label='Import from previous install...',
            command=self.migrate_settings)

        if sys.platform != 'darwin':
            menu_file.add_command(
                label='Exit', command=self.exit_program, accelerator='Alt+F4')
        root.bind_all('<Control-l>', lambda e: self.load_params())
        root.bind_all('<Control-s>', lambda e: self.save_params())

        self.autoclose.set(lnp.userconfig.get_bool('autoClose'))
        menu_options.add_checkbutton(
            label='Close GUI on launch', onvalue=True, offvalue=False,
            variable=self.autoclose, command=self.set_autoclose)

        if update.updates_configured():
            menu_updates = menu_updates = Menu(menubar)
            menu_options.add_cascade(
                menu=menu_updates, label='Check for updates')
            options = [
                "Every launch", "Every day", "Every 3 days", "Every 7 days",
                "Every 14 days", "Every 30 days", "Never"]
            daylist = [0, 1, 3, 7, 14, 30, -1]
            self.updateDays.set(lnp.userconfig.get_number('updateDays'))
            for i, o in enumerate(options):
                menu_updates.add_radiobutton(
                    label=o, value=daylist[i], variable=self.updateDays,
                    command=lambda i=i: self.configure_updates(daylist[i]))
        self.downloadBaselines.set(lnp.userconfig.get_bool('downloadBaselines'))
        menu_options.add_checkbutton(
            label='Allow auto-download of baselines', onvalue=True,
            offvalue=False, variable=self.downloadBaselines,
            command=self.set_downloads)

        self.show_scrollbars.set(lnp.userconfig.get_bool('tkgui_show_scroll'))
        menu_options.add_checkbutton(
            label='Always show scrollbars (reloads program)', onvalue=True,
            offvalue=False, variable=self.show_scrollbars,
            command=self.set_show_scroll)

        menu_run.add_command(
            label='Dwarf Fortress', command=launcher.run_df,
            accelerator='Ctrl+R')
        menu_run.add_command(
            label='Init Editor', command=self.run_init, accelerator='Ctrl+I')
        root.bind_all('<Control-r>', lambda e: launcher.run_df())
        root.bind_all('<Control-i>', lambda e: self.run_init())

        self.populate_menu(
            lnp.config.get_list('folders'), menu_folders,
            launcher.open_folder_idx)
        self.populate_menu(
            lnp.config.get_list('links'), menu_links,
            launcher.open_link_idx)

        menu_help.add_command(
            label="Help", command=self.show_help, accelerator='F1')
        menu_help.add_command(
            label="About", command=self.show_about, accelerator='Alt+F1')
        menu_help.add_command(label="About DF...", command=self.show_df_info)
        root.bind_all('<F1>', lambda e: self.show_help())
        root.bind_all('<Alt-F1>', lambda e: self.show_about())
        root.createcommand('tkAboutDialog', self.show_about)
        return menubar

    def reload_program(self):
        """Reloads the program to allow the user to change DF folders."""
        self.do_reload = True
        self.exit_program()

    def configure_terminal(self, first_run=False):
        """
        Configures the command used to launch a terminal on Linux.
        If first_run is set, a terminal will be selected automatically.
        """
        TerminalSelector(self.root, first_run)

    def configure_updates(self, days):
        """Sets the number of days until next update check."""
        self.updateDays.set(days)
        update.next_update(days)

    def set_downloads(self):
        """Sets the option for auto-download of baselines."""
        baselines.set_auto_download(self.downloadBaselines.get())

    def set_show_scroll(self):
        """
        Toggles if scroll bars should always be shown. Used to work around a
        bug with some themes that modify Windows system files.
        """
        lnp.userconfig['tkgui_show_scroll'] = self.show_scrollbars.get()
        lnp.userconfig.save_data()
        self.reload_program()

    @staticmethod
    def set_autoclose():
        """Toggles automatic closing of the launcher."""
        launcher.toggle_autoclose()

    @staticmethod
    def populate_menu(collection, menu, method):
        """
        Populates a menu with items from a collection.

        Args:
            collection: A collection of menu item data.
            menu: The menu to create the items under.
            method: The method to be called when the menu item is selected.
        """
        #pylint:disable=unused-variable
        for i, f in enumerate(collection):
            if f[0] == '-':
                menu.add_separator()
            else:
                menu.add_command(label=f[0], command=lambda i=i: method(i))

    @staticmethod
    def change_entry(key, var):
        """
        Commits a change for the control specified by key.

        Args:
            key: The key for the control that changed.
            var: The variable bound to the control.
        """
        if not isinstance(key, basestring):
            for k in key:
                TkGui.change_entry(k, var)
            return
        if var.get() != '':
            df.set_option(key, var.get())

    def load_params(self):
        """Reads configuration data."""
        try:
            df.load_params()
        except IOError as e:
            messagebox.showerror(self.root.title(), str(e))
            self.exit_program()
        binding.update()

    @staticmethod
    def save_params():
        """Writes configuration data."""
        df.save_params()

    def exit_program(self):
        """Quits the program."""
        self.root.after_cancel(self.cross_thread_timer)
        self.root.quit()
        self.root.destroy()

    @staticmethod
    def run_program(path):
        """
        Launches another program.

        Args:
            path: Path to the program to launch.
        """
        path = os.path.abspath(path)
        launcher.run_program(path)

    @staticmethod
    def run_df():
        """Launches Dwarf Fortress, reporting any errors when launching."""
        try:
            launcher.run_df()
        except: #pylint: disable=bare-except
            exc_info = sys.exc_info()
            messagebox.showerror(
                title='Error launching Dwarf Fortress',
                message=exc_info[1].message)

    def run_init(self):
        """Opens the init editor."""
        InitEditor(self.root, self)

    @staticmethod
    def show_help():
        """Shows help for the program."""
        if lnp.bundle:
            launcher.open_url('http://pylnp.birdiesoft.dk/docs/'+VERSION+'/')
        else:
            launcher.open_url('http://pylnp.birdiesoft.dk/docs/dev/')

    @staticmethod
    def show_about():
        """Shows about dialog for the program."""
        messagebox.showinfo(
            title='About', message="PyLNP "+VERSION +" - Lazy Newb Pack Python "
            "Edition\n\nPort by Pidgeot\nContributions by PeridexisErrant, "
            "rx80, dricus, James Morgensen, jecowa, carterscottm, McArcady, "
            "fournm, rgov\n\n"
            "Original program: LucasUP, TolyK/aTolyK")

    @staticmethod
    def cycle_option(field):
        """
        Cycles through possible values for an option.

        Args:
            field: The option to cycle.
        """
        if not isinstance(field, basestring):
            for f in field:
                TkGui.cycle_option(f)
            return
        df.cycle_option(field)
        binding.update()

    @staticmethod
    def set_option(field):
        """
        Sets an option directly.

        Args:
            field: The field name to change. The corresponding value is
                automatically read.
        """
        if not isinstance(field, basestring):
            for f in field:
                df.set_option(f, binding.get(field))
        else:
            df.set_option(field, binding.get(field))
        binding.update()

    @staticmethod
    def show_df_info():
        """Shows basic information about the current DF install."""
        messagebox.showinfo(title='DF info', message=str(lnp.df_info))

    def confirm_downloading(self):
        """Ask the user if downloading may proceed."""
        if self.cross_thread_data == 'baselines':
            message = (
                'PyLNP needs to download a copy of Dwarf Fortress to '
                'complete this action. Is this OK?\n\nPlease note: You will '
                'need to retry the action after the download completes.')
            if sys.platform != 'win32':
                message += ('\n\nThe windows_small edition will be used to '
                            'minimise required download size. '
                            'Platform-specific files are discarded.')
        else:
            message = (
                'PyLNP needs to download data to process this action. '
                'Is this OK?\n\nPlease note: You may need to retry the action '
                'after the download completes.')
        self.cross_thread_data = messagebox.askyesno(
            message=message, title='Download data?', icon='question')
        self.reply_semaphore.release()

    def start_download_queue(self, queue):
        """Event handler for starting a download queue."""
        result = True
        if queue == 'baselines':
            if not lnp.userconfig.get_bool('downloadBaselines'):
                self.cross_thread_data = queue
                self.queue.put('<<ConfirmDownloads>>')
                self.reply_semaphore.acquire()
                result = self.cross_thread_data
        elif queue == 'updates':
            result = True
        if result:
            self.queue.put('<<ShowDLPanel>>')
            self.send_update_event(True)
        return result

    def send_update_event(self, force=False):
        """Schedules an update for the download text, if not already pending."""
        if self.update_pending.acquire(force):
            self.queue.put('<<ForceUpdate>>')

    #pylint: disable=unused-argument
    def start_download(self, queue, url, target):
        """Event handler for the start of a download."""
        self.download_text_string = "Downloading %s..." % os.path.basename(url)
        self.send_update_event()

    def update_download_text(self):
        """Updates the text in the download information."""
        s = self.download_text_string
        self.download_text.set(s)
        # Delay to prevent crash from event flood
        self.root.after(200, self.update_pending.release)

    def download_progress(self, queue, url, progress, total):
        """Event handler for download progress."""
        if total != -1:
            self.download_text_string = "Downloading %s... (%s/%s)" % (
                os.path.basename(url), progress, total)
        else:
            self.download_text_string = (
                "Downloading %s... (%s bytes downloaded)" % (
                    os.path.basename(url), progress))
        self.send_update_event(False)

    def end_download(self, queue, url, target, success):
        """Event handler for the end of a download."""
        if success:
            self.download_text_string = "Download finished"
        else:
            self.download_text_string = "Download failed"
        self.send_update_event(True)

    def end_download_queue(self, queue):
        """Event handler for the end of a download queue."""
        self.root.after(5000, lambda: self.root.event_generate(
            '<<HideDLPanel>>', when='tail'))
        self.send_update_event()

    def check_cross_thread(self):
        """Used to raise cross-thread events in the UI thread."""
        while True:
            # pylint:disable=bare-except
            try:
                v = self.queue.get(False)
            except:
                break
            self.root.event_generate(v, when='tail')
        self.cross_thread_timer = self.root.after(100, self.check_cross_thread)

    def restore_defaults(self):
        """Restores default configuration data."""
        if messagebox.askyesno(
                message='Are you sure? '
                'ALL SETTINGS will be reset to game defaults.\n'
                'You may need to re-install graphics afterwards.',
                title='Reset all settings to Defaults?', icon='question'):
            df.restore_defaults()
            messagebox.showinfo(
                self.root.title(),
                'All settings reset to defaults!')

    def on_query_migration(self):
        """If no saves are detected, offer to import from an older pack."""
        if messagebox.askyesno(
                message='Import user content from an older pack?\n'
                'This function will copy saves from an older DF install '
                'or Starter Pack.  It can be used at any time from the '
                'menu File > Import from previous install.',
                title='Import from an older pack?', icon='question'):
            self.migrate_settings()

    def migrate_settings(self):
        """Migrates settings from a previous DF install."""
        old_df = filedialog.askdirectory(
            title='Locate previous DF for import...', mustexist=True)
        if old_df:
            done, msg = importer.do_imports(old_df)
            box = 'Successfully imported:' if done else 'Import failed.'
            messagebox.showinfo(
                self.root.title(),
                '{}\n\n{}\n\nSee the log for more details.'.format(box, msg))

# vim:expandtab
